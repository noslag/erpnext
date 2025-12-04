frappe.ui.form.on('eBay Listing', {
	refresh: function(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__('Sync from eBay'), function() {
				frm.call({
					method: 'sync_from_ebay',
					freeze: true
				});
			});
			
			frm.add_custom_button(__('Push to eBay'), function() {
				frm.call({
					method: 'push_to_ebay',
					freeze: true
				});
			});
		}
	}
});
