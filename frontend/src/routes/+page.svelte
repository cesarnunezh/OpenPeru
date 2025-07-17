<script>
	import Header from '$lib/components/Header.svelte';
	import Footer from '$lib/components/Footer.svelte';
	import bannerImage from '$lib/assets/banner.png';
</script>

<Header />
<div class="">
	<div class="banner has-background-image" style="position: relative; min-height: 400px;">
		<div
			class="banner-image"
			style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1;"
		>
			<img
				src={bannerImage}
				alt="Peruvian Congress building"
				style="width: 100%; height: 100%; object-fit: cover;"
			/>
		</div>
		<div class="banner-content" style="position: relative; z-index: 2; padding: 3rem 1.5rem;">
			<div class="container">
				<div class="banner-text has-text-centered mb-6">
					<h1
						class="title is-1 has-text-white title-font has-text-weight-bold has-text-left"
						style="text-shadow: 2px 2px 4px rgba(0,0,0,0.5);"
					>
						Transparency is trust.<br />Open data on Peruvian politics.
					</h1>
				</div>
				<div class="banner-search">
					<div class="columns is-justify-content-space-between">
						<div class=" represents-search column is-6">
							<div class="box">
								<div class="columns">
									<div class=" column is-8">
										<div class="is-flex is-align-items-center mb-3">
											<div class="mr-3">
												<i class="fa fa-user" aria-hidden="true"></i>
											</div>
											<div>
												<div class="has-text-weight-semibold title-font is-size-5">
													Who Represents You?
												</div>
											</div>
										</div>
										<input type="text" placeholder="Enter your district..." class="input" />
									</div>
									<div class="column is-4 is-flex is-align-items-end">
										<button class="button is-primary is-fullwidth">Search</button>
									</div>
								</div>
							</div>
						</div>
						<div class="bills-search column is-6">
							<div class="box">
								<div class="columns">
									<div class=" column is-8">
										<div class="is-flex is-align-items-center mb-3">
											<div class="mr-3">
												<i class="fa fa-file-text" aria-hidden="true"></i>
											</div>
											<div>
												<div class="has-text-weight-semibold title-font is-size-5">
													Track and Search Bills
												</div>
											</div>
										</div>
										<input type="text" placeholder="Enter a bill name or topic..." class="input" />
									</div>
									<div class="column is-4 is-flex is-align-items-end">
										<button class="button is-primary is-fullwidth">Search</button>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
	<div class="data contatier is-flex is-justify-content-center">
		<div class="section column is-4">
			<a href="/data" class="has-text-dark" style="text-decoration: none;">
				<div class="is-flex is-align-items-center mb-3">
					<div class="mr-3">
						<i class="fa fa-table" aria-hidden="true"></i>
					</div>
					<div>
						<div class="has-text-weight-semibold is-size-5 title-font">Access the Data</div>
					</div>
				</div>
				<div>
					We make all of our data available for bulk download and via our powerful APIs. Get an API
					key to get started.
				</div>
			</a>
		</div>
	</div>
</div>
<Footer />
