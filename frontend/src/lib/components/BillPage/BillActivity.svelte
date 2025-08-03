<script>
	let { billEvents = { title: 'blank' } } = $props();
	import BillActivityPanel from '$lib/components/BillPage/BillActivityPanel.svelte';
	console.log('Bill Events:', billEvents);
</script>

{#each billEvents.steps as step}
	<BillActivityPanel {step} />
{/each}
