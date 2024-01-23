# Copyright (c) 2024, Ecosoft, Kitti U.
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.utils import flt

import erpnext

salary_slip = frappe.qb.DocType("Salary Slip")
salary_detail = frappe.qb.DocType("Salary Detail")
salary_component = frappe.qb.DocType("Salary Component")


def execute(filters=None):
	if not filters:
		filters = {}

	currency = None
	if filters.get("currency"):
		currency = filters.get("currency")
	company_currency = erpnext.get_company_currency(filters.get("company"))

	salary_slips = get_salary_slips(filters, company_currency)
	if not salary_slips:
		return [], []

	earning_types, ded_types = get_earning_and_deduction_types(salary_slips)
	columns = get_columns()

	ss_earning_map = get_salary_slip_details(salary_slips, currency, company_currency, "earnings")
	ss_ded_map = get_salary_slip_details(salary_slips, currency, company_currency, "deductions")

	doj_map = get_employee_doj_map()

	data = []
	# Calculate totals for cards
	totals = {"gross_pay": 0, "net_pay": 0, "sso": 0, "tax": 0, "edu": 0, "penalty": 0}
	sc_sso = "หักเงินประกันสังคม"
	sc_tax = "หักเงินภาษีบุคคลธรรมดา"
	sc_edu = "หักเงินกยศ"
	sc_penalties = ["หักเงินลาเกินสิทธิ์", "หักเงินอื่นๆ"]  # penalties are deducted without having to pay anyone
	# --

	for ss in salary_slips:
		row = {
			"indent": 0,
			"salary_slip_id": ss.name,
			"employee": ss.employee,
			"employee_name": ss.employee_name,
			"data_of_joining": doj_map.get(ss.employee),
			"department": ss.department,
			"designation": ss.designation,
			"start_date": ss.start_date,
			"end_date": ss.end_date,
			"currency": currency or company_currency,
		}

		update_column_width(ss, columns)

		if currency == company_currency:
			row.update(
				{
					"gross_pay": flt(ss.gross_pay) * flt(ss.exchange_rate),
					"total_deduction": flt(ss.total_deduction) * flt(ss.exchange_rate),
					"net_pay": flt(ss.net_pay) * flt(ss.exchange_rate),
				}
			)

		else:
			row.update(
				{"gross_pay": ss.gross_pay, "total_deduction": ss.total_deduction, "net_pay": ss.net_pay}
			)

		totals["gross_pay"] += row["gross_pay"]
		totals["net_pay"] += row["net_pay"]

		data.append(row)

		# Loop through all salary component, sorted by amount
		j = max(len(earning_types), len(ded_types))
		earns = []
		deducts =[]
		# Prepare to sort by amount
		for i in range(0, j):
			if i < len(earning_types):
				earns.append((earning_types[i], ss_earning_map.get(ss.name, {}).get(earning_types[i])))
			if i < len(ded_types):
				deducts.append((ded_types[i], ss_ded_map.get(ss.name, {}).get(ded_types[i])))
		earns = sorted(earns, key=lambda tup: tup[1], reverse=True)
		deducts = sorted(deducts, key=lambda tup: tup[1], reverse=True)
		# Create row
		for i in range(0, j):
			row = {"indent": 1}
			if i < len(earns):
				row.update({"earn_type": earns[i][0], "gross_pay": earns[i][1]})
			if i < len(deducts):
				row.update({"deduct_type": deducts[i][0], "total_deduction": deducts[i][1]})
			# Total cards
			if row.get("deduct_type") == sc_sso:
				totals["sso"] += deducts[i][1]
			if row.get("deduct_type") == sc_tax:
				totals["tax"] += deducts[i][1]
			if row.get("deduct_type") == sc_edu:
				totals["edu"] += deducts[i][1]
			if row.get("deduct_type") in sc_penalties:
				totals["penalty"] += deducts[i][1]
			data.append(row)

	message = get_message(totals)
	return columns, data, message, None, None


def get_earning_and_deduction_types(salary_slips):
	salary_component_and_type = {_("Earning"): [], _("Deduction"): []}

	for salary_component in get_salary_components(salary_slips):
		component_type = get_salary_component_type(salary_component)
		salary_component_and_type[_(component_type)].append(salary_component)

	return sorted(salary_component_and_type[_("Earning")]), sorted(
		salary_component_and_type[_("Deduction")]
	)


def update_column_width(ss, columns):
	if ss.department is not None:
		columns[4].update({"width": 120})
	if ss.designation is not None:
		columns[5].update({"width": 120})

def get_columns():
	columns = [
		{
			"label": _("Salary Slip ID"),
			"fieldname": "salary_slip_id",
			"fieldtype": "Link",
			"options": "Salary Slip",
			"width": 150,
		},
		{
			"label": _("Employee"),
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 120,
		},
		{
			"label": _("Employee Name"),
			"fieldname": "employee_name",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": _("Date of Joining"),
			"fieldname": "data_of_joining",
			"fieldtype": "Date",
			"width": 80,
		},
		{
			"label": _("Department"),
			"fieldname": "department",
			"fieldtype": "Link",
			"options": "Department",
			"width": -1,
		},
		{
			"label": _("Designation"),
			"fieldname": "designation",
			"fieldtype": "Link",
			"options": "Designation",
			"width": -1,
		},
		{
			"label": _("Start Date"),
			"fieldname": "start_date",
			"fieldtype": "Data",
			"width": 80,
		},
		{
			"label": _("End Date"),
			"fieldname": "end_date",
			"fieldtype": "Data",
			"width": 80,
		},
		{
			"label": _("Earn Type"),
			"fieldname": "earn_type",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Gross Pay"),
			"fieldname": "gross_pay",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"label": _("Deduct Type"),
			"fieldname": "deduct_type",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Total Deduction"),
			"fieldname": "total_deduction",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"label": _("Net Pay"),
			"fieldname": "net_pay",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"label": _("Currency"),
			"fieldtype": "Data",
			"fieldname": "currency",
			"options": "Currency",
			"hidden": 1,
		},
	]
	return columns


def get_salary_components(salary_slips):
	return (
		frappe.qb.from_(salary_detail)
		.where(salary_detail.parent.isin([d.name for d in salary_slips]))
		.select(salary_detail.salary_component)
		.distinct()
	).run(pluck=True)


def get_salary_component_type(salary_component):
	return frappe.db.get_value("Salary Component", salary_component, "type", cache=True)


def get_salary_slips(filters, company_currency):
	doc_status = {"Draft": 0, "Submitted": 1, "Cancelled": 2}

	query = frappe.qb.from_(salary_slip).select(salary_slip.star)

	if filters.get("docstatus"):
		query = query.where(salary_slip.docstatus == doc_status[filters.get("docstatus")])

	if filters.get("from_date"):
		query = query.where(salary_slip.start_date >= filters.get("from_date"))

	if filters.get("to_date"):
		query = query.where(salary_slip.end_date <= filters.get("to_date"))

	if filters.get("company"):
		query = query.where(salary_slip.company == filters.get("company"))

	if filters.get("employee"):
		query = query.where(salary_slip.employee == filters.get("employee"))

	if filters.get("currency") and filters.get("currency") != company_currency:
		query = query.where(salary_slip.currency == filters.get("currency"))

	salary_slips = query.run(as_dict=1)

	return salary_slips or []


def get_employee_doj_map():
	employee = frappe.qb.DocType("Employee")
	result = (frappe.qb.from_(employee).select(employee.name, employee.date_of_joining)).run()
	return frappe._dict(result)


def get_salary_slip_details(salary_slips, currency, company_currency, component_type):
	salary_slips = [ss.name for ss in salary_slips]

	result = (
		frappe.qb.from_(salary_slip)
		.join(salary_detail)
		.on(salary_slip.name == salary_detail.parent)
		.where((salary_detail.parent.isin(salary_slips)) & (salary_detail.parentfield == component_type))
		.select(
			salary_detail.parent,
			salary_detail.salary_component,
			salary_detail.amount,
			salary_slip.exchange_rate,
		)
	).run(as_dict=1)

	ss_map = {}

	for d in result:
		ss_map.setdefault(d.parent, frappe._dict()).setdefault(d.salary_component, 0.0)
		if currency == company_currency:
			ss_map[d.parent][d.salary_component] += flt(d.amount) * flt(
				d.exchange_rate if d.exchange_rate else 1
			)
		else:
			ss_map[d.parent][d.salary_component] += flt(d.amount)

	return ss_map


def get_message(totals):
	return """
    <div class="col-xs-12 column-break">
        <table class="table table-condensed">
          <thead>
            <tr>
              <th style="width: 150px" class="text-center">เงินเดือน</th>
              <th style="width: 150px" class="text-center">ประกันสังคม</th>
              <th style="width: 150px" class="text-center">รวมยอดเบิก</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="text-center">
                <div class="value">%s</div>
              </td>
              <td class="text-center">
                <div class="value">%s</div>
              </td>
              <td class="text-center">
                <div style="font-weight: bold" class="value">%s</div>
              </td>
            </tr>
          </tbody>
        </table>

        <table class="table table-condensed">
          <thead>
            <tr>
              <th style="width: 150px" class="text-center">ธนาคารไทยพานิชย์เพื่อเงินเดือนพนักงาน</th>
              <th style="width: 80px" class="text-center">สำนักงานประกันสังคม</th>
              <th style="width: 80px" class="text-center">กรมสรรพากร</th>
              <th style="width: 150px" class="text-center">กรมสรรพากร 2 เพื่อรับชำระเงินคืนกยศ.</th>
              <th style="width: 80px" class="text-center">รวมยอดจ่าย</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="text-center">
                <div class="value">%s</div>
              </td>
              <td class="text-center">
                <div class="value">%s</div>
              </td>
              <td class="text-center">
                <div class="value">%s</div>
              </td>
              <td class="text-center">
                <div class="value">%s</div>
              </td>
              <td class="text-center">
                <div style="font-weight: bold" class="value">%s</div>
              </td>
            </tr>
          </tbody>
        </table>
    </div>
	""" % (
		# Amount to be paid
		frappe.format(totals["gross_pay"]-totals["penalty"], "Currency"),
		frappe.format(totals["sso"], "Currency"),
		frappe.format(totals["gross_pay"]-totals["penalty"]+totals["sso"], "Currency"),
		# Payout to parties
		frappe.format(totals["net_pay"], "Currency"),
		frappe.format(totals["sso"] * 2, "Currency"),
		frappe.format(totals["tax"], "Currency"),
		frappe.format(totals["edu"], "Currency"),
		frappe.format(totals["net_pay"]+(totals["sso"]*2)+totals["tax"]+totals["edu"], "Currency"),
	)
