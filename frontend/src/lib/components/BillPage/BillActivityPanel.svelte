<script>
	let { step = [] } = $props();

	const icons = {
		Introduced: 'fa fa-check',
		'In committee': 'fa fa-comment',
		Vote: 'fa fa-pencil-alt'
	};
	console.log('Step data:', step);
</script>

<div class="box">
	<div class="columns is-mobile">
		<div class="column is-narrow">
			<span class="icon">
				<i class="fa fa-circle"></i>
			</span>
		</div>
		<div class="column">
			<div class="is-flex is-flex-direction-column">
				<h5 class="title is-5">{step.step_type}</h5>
				<p class="subtitle is-6">{step.step_details || 'Activity text'}</p>
			</div>
		</div>
		{#if step.step_type == 'Vote'}
			<div class="column is-narrow">
				<div class="columns is-mobile">
					<div class="column has-text-centered">
						<p class="has-text-success has-text-weight-bold">Yes</p>
						<p>{step.yes_votes || 0}</p>
					</div>
					<div class="column has-text-centered">
						<p class="has-text-danger has-text-weight-bold">No</p>
						<p>{step.no_votes || 0}</p>
					</div>
					<div class="column has-text-centered">
						<p class="has-text-grey has-text-weight-bold">Abstain</p>
						<p>{step.abstain_votes || 0}</p>
					</div>
				</div>
			</div>
		{/if}
	</div>
</div>
