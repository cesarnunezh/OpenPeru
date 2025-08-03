<script>
	let { bill = { title: 'Loading..' } } = $props();
</script>

<div class="is-flex is-justify-content-space-between is-align-items-center">
	<div class="is-flex-direction-column has-text-left is-column-half">
		<div class="title is-4 mb-1">{bill.title || 'error'}</div>
		<div class="subtitle is-6 mb-1">Sponsored by: {bill.author_id || 'error'}</div>
		<div class="has-text-grey">Introduced in: {bill.leg_period || 'error'}</div>
	</div>
	<div class="field">
		<div class="control has-icons-left">
			<input class="input" type="text" placeholder="Search..." />
			<span class="icon is-small is-left">
				<i class="fa fa-search"></i>
			</span>
		</div>
	</div>
</div>
