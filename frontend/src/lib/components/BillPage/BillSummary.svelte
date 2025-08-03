<script>
	let { bill = { title: 'blank' } } = $props();
</script>

<div class="box">
	<div class="content">
		<div class="title is-5 mb-2">Summary:</div>
		<p class="summary-text">{bill.summary || 'No summary available'}</p>
	</div>

	<div class="content">
		<div class="title is-5 mb-2">Coauthors:</div>
		{#if bill.coauthors && bill.coauthors.length > 0}
			{bill.coauthors || 'No coauthors listed'}
		{:else}
			<p>No coauthors listed</p>
		{/if}
	</div>
</div>
