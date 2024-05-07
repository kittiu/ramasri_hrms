import frappe


def get_payroll_summary_by_component(payroll_entry, prev=0):
	""" 
	This function is being used for Printing Payroll Entry Summary form
	prev = previous month, i.e., 1 months before, 2 months before
	return {
		"payroll_entry": {"name": "PE-0001", "posting_date": "2023-01-02"},
		"earnings": {"c1": 100, "c2": 200},
		"deductions": {"c1": 100, "c2": 200},
	}
	"""
	if prev:
		prev_docs = frappe.db.get_all(
			"Payroll Entry",
			filters={
				"docstatus": ["!=", 2],
				"start_date": ["<", payroll_entry.start_date]
			},
			order_by="start_date desc",
			limit=prev,
			pluck="name"
		)
		prev_doc = prev_docs[prev-1: prev]
		if not prev_doc:
			return {}
		payroll_entry = frappe.get_doc("Payroll Entry", prev_doc[0])
	rows = frappe.db.sql("""
		select * from (
			select pe.posting_date, sd.parentfield, sd.salary_component, sum(sd.amount) amount
			from `tabSalary Slip` ss join `tabSalary Detail` sd on sd.parent = ss.name
				join `tabPayroll Entry` pe on pe.name = ss.payroll_entry
			where ss.payroll_entry = %s
				and ss.docstatus != 2
				and pe.docstatus != 2
		group by pe.posting_date, sd.parentfield, sd.salary_component
		) a
		order by a.parentfield desc, a.amount desc
	""", (payroll_entry.name,))
	res = {
		"payroll_entry": {"name": payroll_entry.name, "posting_date": False, "month": False, "year": False},
		"earnings": {"total": 0},
		"deductions": {"total": 0},
	}
	if rows:
		res["payroll_entry"]["posting_date"] = rows[0][0].strftime("%Y-%m-%d")
		res["payroll_entry"]["month"] = 'x มกราคม กุมภาพันธ์ มีนาคม เมษายน พฤษภาคม มิถุนายน กรกฎาคม สิงหาคม กันยายน ตุลาคม พฤศจิกายน ธันวาคม'.split()[rows[0][0].month]
		res["payroll_entry"]["year"] = rows[0][0].year + 543
	for row in rows:
		res[row[1]][row[2]] = row[3]  # res["earnings"] = {component: amount}
		res[row[1]]["total"] += row[3]
	return res


