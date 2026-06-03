import sys
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from backend.config import settings
from backend.core.enums import TypeBillStep
from backend.database import models, raw_models
from backend.scrapers.utils import get_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy import String, cast, create_engine, select
from zoneinfo import ZoneInfo
from loguru import logger

_VLLM_MANAGER = None
_VLLM_MANAGER_LOCK = Lock()


def get_approved_ids(
    db_session_factory: sessionmaker,
    model: type,
    limit: int = 15,
) -> list[str]:
    """
    Get all approved bill_id
    """
    with db_session_factory() as db:
        stmt = (
            select(model.id)
            .where(model.bill_approved.is_(True))
            .order_by(model.id.desc())
            .limit(limit)
        )
        return list(db.scalars(stmt))


def get_approved_bill_documents(
    db_session_factory: sessionmaker,
    limit: int = 15,
):
    """
    Get approved variables from raw_bill_documents
    """
    approved_ids = get_approved_ids(db_session_factory, models.Bill, limit=limit)
    if not approved_ids:
        return []

    step_types = [
        TypeBillStep.PRESENTADO,
        TypeBillStep.TEXTO_SUSTITUTORIO_O_REVISION,
        TypeBillStep.AUTOGRAFA,
    ]

    step_filter = (
        select(
            models.BillStep.bill_id,
            cast(models.BillStep.step_id, String).label("step_id"),
        )
        .where(
            models.BillStep.bill_id.in_(approved_ids),
            models.BillStep.step_type.in_(step_types),
            models.BillStep.vote_step.is_(False),
        )
        .subquery()
    )

    with db_session_factory() as db:
        return list(
            db.scalars(
                select(raw_models.RawBillDocument)
                .join(
                    step_filter,
                    (raw_models.RawBillDocument.bill_id == step_filter.c.bill_id)
                    & (raw_models.RawBillDocument.step_id == step_filter.c.step_id),
                )
                .where(raw_models.RawBillDocument.processed.is_(False))
            )
        )


def _get_vllm_manager():
    global _VLLM_MANAGER
    with _VLLM_MANAGER_LOCK:
        if _VLLM_MANAGER is None:
            from chandra.model import InferenceManager

            logger.info("Loading Chandra OCR 2 model...")
            _VLLM_MANAGER = InferenceManager(method="vllm")
            logger.info("Model loaded successfully.")
    return _VLLM_MANAGER


def _normalize_congreso_url(url: str) -> str:
    if url.startswith("https://wb2server.congreso.gob.pe/"):
        return url.replace(
            "https://wb2server.congreso.gob.pe/",
            "https://api.congreso.gob.pe/",
            1,
        )
    return url


def _get_images_from_pdf(pdf_source: str | bytes):
    import fitz
    from PIL import Image

    input_images = []
    if isinstance(pdf_source, (bytes, bytearray)):
        source_label = "bytes"
        pdf_context = fitz.open(stream=pdf_source, filetype="pdf")
    else:
        source_label = pdf_source
        pdf_context = fitz.open(pdf_source)

    with pdf_context as pdf_document:
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            pix = page.get_pixmap(dpi=300)
            img_data = pix.samples
            img_width = pix.width
            img_height = pix.height
            pil_image = Image.frombytes("RGB", [img_width, img_height], img_data)
            input_images.append(pil_image)

    logger.info(f"Converted {len(input_images)} page(s) from {source_label} to images.")
    return input_images


def chandra2_vllm(url: str):
    """
    Generate OCR text per page using the Chandra vLLM model.
    """
    from chandra.model.schema import BatchInputItem

    if not url or not url.startswith(("http://", "https://")):
        raise ValueError(f"Expected an HTTP(S) URL, got {url!r}")

    url = _normalize_congreso_url(url)
    response = get_url(url)
    if response is None:
        raise RuntimeError(f"Failed to download PDF from {url}")
    pdf_source = response.content

    images = _get_images_from_pdf(pdf_source)
    if not images:
        raise RuntimeError("No images rendered from PDF source")

    batch = [BatchInputItem(image=img, prompt_type="ocr_layout") for img in images]
    manager = _get_vllm_manager()
    results = manager.generate(
        batch, include_headers_footers=False, include_images=False
    )
    return [
        {"page_num": idx + 1, "text": result.markdown}
        for idx, result in enumerate(results)
    ]


def write_raw_bill_pages(
    db_session_factory: sessionmaker,
    raw_docs: list[raw_models.RawBillDocument],
    ocr_model: str = "chandra2",
) -> int:
    if not raw_docs:
        logger.info("No raw bill documents provided.")
        return 0

    if ocr_model != "chandra2":
        raise RuntimeError(f"Unsupported OCR model: {ocr_model}. Expected 'chandra2'.")

    def _process_doc(doc: raw_models.RawBillDocument) -> int:
        now = datetime.now(ZoneInfo("America/Lima"))
        created = 0
        try:
            with db_session_factory() as db:
                existing_page = db.scalar(
                    select(raw_models.RawBillPage.page_num)
                    .where(
                        raw_models.RawBillPage.bill_id == doc.bill_id,
                        raw_models.RawBillPage.step_id == doc.step_id,
                        raw_models.RawBillPage.file_id == doc.file_id,
                        raw_models.RawBillPage.ocr_model == ocr_model,
                    )
                    .limit(1)
                )
                if existing_page is not None:
                    raw_doc = db.get(
                        raw_models.RawBillDocument,
                        (doc.bill_id, doc.step_id, doc.file_id),
                    )
                    if raw_doc:
                        raw_doc.processed = True
                        db.commit()  # commmit if the document existed
                    return 0

                pages = chandra2_vllm(doc.url)
                for page in pages:
                    page_num = page["page_num"]
                    text = page["text"]

                    db.add(
                        raw_models.RawBillPage(
                            bill_id=doc.bill_id,
                            step_id=doc.step_id,
                            file_id=doc.file_id,
                            page_num=page_num,
                            text=text,
                            ocr_model=ocr_model,
                            timestamp=now,
                            last_update=True,
                            changed=False,
                            processed=False,
                        )
                    )
                    created += 1

                raw_doc = db.get(
                    raw_models.RawBillDocument,
                    (doc.bill_id, doc.step_id, doc.file_id),
                )
                if raw_doc:
                    raw_doc.processed = True
                db.commit()  # commmit after every document
                logger.info(
                    f"commited bill_id {doc.bill_id} step_id {doc.step_id} file_id {doc.file_id} pages {len(pages)}"
                )
        except Exception:
            logger.exception(
                "Failed to process doc bill_id={} step_id={} file_id={}",
                doc.bill_id,
                doc.step_id,
                doc.file_id,
            )
            return 0

        return created

    workers = 6
    created_total = 0
    _get_vllm_manager()
    logger.info("Processing {} documents with {} workers", len(raw_docs), workers)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_process_doc, doc) for doc in raw_docs]
        for future in as_completed(futures):
            try:
                created_total += future.result()
            except Exception:
                logger.exception("Worker crashed unexpectedly")

    logger.info("Created {} pages", created_total)
    return created_total


if __name__ == "__main__":
    limit = 15
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError as exc:
            raise ValueError("limit must be an integer") from exc

    db_engine = create_engine(settings.DB_URL, pool_pre_ping=True)
    db_session_factory = sessionmaker(
        bind=db_engine,
        autocommit=False,
        autoflush=False,
    )

    approved_docs = get_approved_bill_documents(db_session_factory, limit=limit)
    logger.info(f"len approved docs {len(approved_docs)}")
    write_raw_bill_pages(db_session_factory, approved_docs, ocr_model="chandra2")
