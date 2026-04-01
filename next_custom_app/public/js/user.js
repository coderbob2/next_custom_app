// User doctype customizations for Next Custom App

frappe.ui.form.on("User", {
    refresh(frm) {
        frm.set_query("custom_suspense_account", function () {
            return {
                filters: {
                    is_group: 1,
                    account_type: "Cash",
                },
            };
        });
    },
});
