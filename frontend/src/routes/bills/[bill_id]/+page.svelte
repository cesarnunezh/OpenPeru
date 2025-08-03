<script>
	import Header from '$lib/components/Header.svelte';
	import Footer from '$lib/components/Footer.svelte';
	import BillHeader from '$lib/components/BillPage/BillHeader.svelte';
	import BillActivity from '$lib/components/BillPage/BillActivity.svelte';
	import BillSummary from '$lib/components/BillPage/BillSummary.svelte';

	import { API_URL } from '$lib/store.js';
	import { page } from '$app/state';
	import { onMount } from 'svelte';

	let billData = $state({});
	let billEventsData = $state({});
	let bill = $derived(billData.data);
	let billEvents = $derived(billEventsData.data);

	onMount(async () => {
		const response = await fetch(`${API_URL}/bills/${page.params.bill_id}`);

		if (response.ok) {
			billData = await response.json();
		} else {
			console.error('Failed to load bill data');
		}

		const eventsResponse = await fetch(`${API_URL}/events?bill_id=${page.params.bill_id}`);
		if (eventsResponse.ok) {
			billEventsData = await eventsResponse.json();
		} else {
			console.error('Failed to load bill events');
		}
	});

	// inspect
	$inspect('Bill data loaded:', bill);
	$inspect('Bill events loaded:', billEvents);
</script>

<Header />
<div class="container">
	<div class="p-5">
		<BillHeader {bill} />
	</div>
	<hr />
	<div class="bill-content columns">
		<div class="column is-half">
			<div class="section">
				<BillSummary {bill} />
			</div>
		</div>
		<div class="column is-half">
			<div class="sect">
				<BillActivity {billEvents} />
			</div>
		</div>
	</div>
</div>

<Footer />

<style>
</style>
