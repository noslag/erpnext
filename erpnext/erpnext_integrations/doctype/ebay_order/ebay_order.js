frappe.ui.form.on('eBay Order', {
	refresh: function(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__('Sync from eBay'), function() {
				frm.call({
					method: 'sync_from_ebay',
					freeze: true
				});
			});
		}
	}
});
