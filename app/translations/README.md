# Translations: updating and compiling with pybabel

This document explains how to extract messages, update or initialize `.po` files, and compile them using `pybabel`.

Prerequisites
- Activate your virtualenv from the project root (if using one).
- Install Babel (and Flask-Babel if needed):

```bash
pip install Babel Flask-Babel
```

Typical workflow (from the project root)

1. Extract messages to a POT file

If you need to regenerate the message template, run:

```bash
pybabel extract -F app/babel.cfg -o app/messages.pot app
```

This reads the source files under `app/` using `app/babel.cfg` and writes `app/messages.pot`.

2. Update existing catalogs (when messages.pot changed)

```bash
pybabel update -i app/messages.pot -d translations
```

This merges new or changed messages into existing `.po` files under `translations/`.

3. Edit `.po` files

Open `translations/<lang_code>/LC_MESSAGES/messages.po` in your editor or a .po editor (Poedit), translate strings, then save.

4. Compile `.po` files into `.mo` (required for runtime)

```bash
pybabel compile -d translations
```

Or compile a single language:

```bash
pybabel compile -d translations -l es
```