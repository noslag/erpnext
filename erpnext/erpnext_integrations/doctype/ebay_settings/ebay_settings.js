frappe.ui.form.on('eBay Settings', {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.enabled) {
			add_connection_button(frm);
			update_connection_status(frm);
			frm.set_intro(__("RuName and Client ID are managed centrally; tenants only authorize their own store."));
		} else {
			frm.dashboard.clear_headline();
		}
	},

	enabled(frm) {
		if (frm.doc.enabled) {
			frm.dashboard.set_headline(__('Save and click "Connect eBay Store" to authorize.'));
		} else {
			frm.dashboard.clear_headline();
		}
	},
});

function add_connection_button(frm) {
	const label = frm.doc.refresh_token ? __('Reconnect eBay Store') : __('Connect eBay Store');
	frm.add_custom_button(label, () => {
		if (frm.is_dirty()) {
			frappe.msgprint(__('Please save the document before starting the eBay connection.'));
			return;
		}

		frm.call({
			method: 'erpnext.erpnext_integrations.ebay.oauth.start_authorization_flow',
			freeze: true,
			callback: (r) => {
				const url = r?.message?.authorization_url;
				if (!url) {
					frappe.msgprint(__('Failed to build authorization URL. Check the server logs.'));
					return;
				}
				window.open(url, 'ebay_oauth', 'width=600,height=700,resizable=yes');
			},
		});
	});
}

function update_connection_status(frm) {
	if (frm.doc.refresh_token) {
		let message = __('Connected to eBay.');
		if (frm.doc.access_token_expires_at) {
			const expires = frappe.datetime.str_to_user(frm.doc.access_token_expires_at);
			message = __('Connected to eBay. Access token expires at {0}.', [expires]);
		}
		frm.dashboard.set_headline(message, 'green');
	} else {
		frm.dashboard.set_headline(__('Not connected to eBay. Click "Connect eBay Store" to continue.'), 'orange');
	}
}
