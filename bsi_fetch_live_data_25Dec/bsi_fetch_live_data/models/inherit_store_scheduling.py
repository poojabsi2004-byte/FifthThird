# -*- coding: utf-8 -*-

from odoo import models, api, fields
from datetime import datetime, timedelta, time
import requests
import logging
from odoo.http import request
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class InheritStoreScheduling(models.Model):
    _inherit = 'store.scheduling'

    last_updated_on_api = fields.Datetime(string="Last Updated On API")
    is_updated = fields.Boolean(string="Is Updated ?")

    def chunk_list(self, input_list, chunk_size):
        for i in range(0, len(input_list), chunk_size):
            yield input_list[i:i + chunk_size]

    def action_store_scheduling(self):
        channel = self.env['discuss.channel'].sudo().search([('name', '=', 'Subway Scheduling Logs')], limit=1)
        if not channel:
            channel = self.env['discuss.channel'].sudo().create({
                "name": 'Subway Scheduling Logs',
                "channel_type": "channel",
                "channel_partner_ids": [(4, self.env.user.partner_id.id)],
            })

        # ============ GET API KEYS ============ #
        api_key_two = self.env['ir.config_parameter'].sudo().get_param('bsi_fetch_live_data.account_two_api_key')
        client_key_two = self.env['ir.config_parameter'].sudo().get_param('bsi_fetch_live_data.account_two_api_client')
        api_key_three = self.env['ir.config_parameter'].sudo().get_param('bsi_fetch_live_data.account_three_api_key')
        client_key_three = self.env['ir.config_parameter'].sudo().get_param('bsi_fetch_live_data.account_three_api_client')

        account_two_keys_missing = not api_key_two or not client_key_two
        account_three_keys_missing = not api_key_three or not client_key_three

        if account_two_keys_missing and account_three_keys_missing:
            msg = "Error: Missing API Key or Client Key for both Account TWO and Account THREE in system parameters."
            _logger.error(msg)
            channel.message_post(body=msg)
            raise UserError(msg)
        elif account_two_keys_missing:
            msg = "Error: Missing API Key or Client Key for Account TWO in system parameters."
            _logger.error(msg)
            channel.message_post(body=msg)
        elif account_three_keys_missing:
            msg = "Error: Missing API Key or Client Key for Account THREE in system parameters."
            _logger.error(msg)
            channel.message_post(body=msg)

        # Process each record in self (supports multi-record selection)
        for record in self:
            start_date = record.week_starting_date
            end_date = record.week_ending_date
            store_number = str(record.store_number) if record.store_number else None

            if not start_date or not end_date or not store_number:
                msg = f"Error: Missing required data for store {store_number or 'Unknown'}. Need week_starting_date, week_ending_date, and store_number."
                channel.message_post(body=msg)
                continue

            print(f"Processing Store: {store_number}, Start: {start_date}, End: {end_date}")

            # Try Account TWO first
            data_fetched = False
            
            if not account_two_keys_missing:
                HEADERS_ACCOUNT_TWO = {
                    "api-client": str(client_key_two),
                    "api-key": str(api_key_two)
                }

                try:
                    # Fetch restaurants to verify store exists in this account
                    res = requests.get("https://liveiqfranchiseeapi.subway.com/api/Restaurants", headers=HEADERS_ACCOUNT_TWO)
                    if res.status_code == 200:
                        restaurants = res.json()
                        store_exists = any(str(r.get('restaurantNumber')) == store_number for r in restaurants)
                        
                        if store_exists:
                            # Fetch Sales Summary
                            sales_url = f"https://liveiqfranchiseeapi.subway.com/api/SalesSummary/{store_number}/startDate/{start_date}/endDate/{end_date}"
                            sales_response = requests.get(sales_url, headers=HEADERS_ACCOUNT_TWO)
                            
                            if sales_response.status_code == 200:
                                summary = sales_response.json()
                                summary_data_list = summary.get('data', [])
                                for summary_data in summary_data_list:
                                    net_sales = summary_data.get('netSales', 0.0)
                                    payroll_taxes = summary_data.get('tax', 0.0)
                                    total_worked_hours = summary_data.get('hoursWorked', 0.0)
                                    
                                    record.write({
                                        'net_sales': net_sales,
                                        'total_worked_hours': total_worked_hours,
                                        'allowed_percentage_food_cost': 27,
                                        'last_updated_on_api': datetime.now(),
                                        'is_updated': True,
                                    })
                                    msg = f"Account TWO: Updated store {store_number} with Net Sales: {net_sales}, Tax: {payroll_taxes}, Hours: {total_worked_hours}"
                                    channel.message_post(body=msg)
                                    data_fetched = True

                            # Fetch Control Sheet
                            controlsheet_url = f"https://liveiqfranchiseeapi.subway.com/api/controlsheet/{store_number}/{end_date}"
                            controlsheet_response = requests.get(controlsheet_url, headers=HEADERS_ACCOUNT_TWO)
                            
                            if controlsheet_response.status_code == 200:
                                control = controlsheet_response.json()
                                control_data_list = control.get('data', [])
                                for control_data in control_data_list:
                                    summary = control_data.get('summary', {})
                                    productivity = summary.get('productivity')
                                    cashControl = control_data.get('cashControl', {})
                                    debit = cashControl.get('debit', {})
                                    debit_total = debit.get('total')
                                    
                                    record.write({
                                        'payroll_productivity': productivity,
                                        'paychex_total_debit': debit_total,
                                    })
                                    msg = f"Account TWO: Updated store {store_number} with Productivity: {productivity}, Debit Total: {debit_total}"
                                    channel.message_post(body=msg)

                            # Fetch Tips
                            tips_url = f"https://liveiqfranchiseeapi.subway.com/api/TipsDetails/{store_number}/startDate/{start_date}/endDate/{end_date}"
                            tips_response = requests.get(tips_url, headers=HEADERS_ACCOUNT_TWO)
                            
                            if tips_response.status_code == 200:
                                tips = tips_response.json()
                                tips_data_list = tips.get('data', [])
                                total_employee_split_tip = sum(tip_data.get('employeeSplitTip', 0.0) for tip_data in tips_data_list)
                                
                                record.write({'total_tips': total_employee_split_tip})
                                msg = f"Account TWO: Updated store {store_number} with Total Tips: {total_employee_split_tip}"
                                channel.message_post(body=msg)
                            
                except Exception as e:
                    _logger.exception(f"Error fetching data from Account TWO for store {store_number}")
                    channel.message_post(body=f"Exception (Account TWO) for store {store_number}: {str(e)}")

            # Try Account THREE if data not fetched from Account TWO
            if not data_fetched and not account_three_keys_missing:
                HEADERS_ACCOUNT_THREE = {
                    "api-client": str(client_key_three),
                    "api-key": str(api_key_three)
                }

                try:
                    # Fetch restaurants to verify store exists in this account
                    res = requests.get("https://liveiqfranchiseeapi.subway.com/api/Restaurants", headers=HEADERS_ACCOUNT_THREE)
                    if res.status_code == 200:
                        restaurants = res.json()
                        store_exists = any(str(r.get('restaurantNumber')) == store_number for r in restaurants)
                        
                        if store_exists:
                            # Fetch Sales Summary (Note: URL has 'end_date' instead of 'endDate' - using Account THREE pattern)
                            sales_url = f"https://liveiqfranchiseeapi.subway.com/api/SalesSummary/{store_number}/startDate/{start_date}/endDate/{end_date}"
                            sales_response = requests.get(sales_url, headers=HEADERS_ACCOUNT_THREE)
                            
                            if sales_response.status_code == 200:
                                summary = sales_response.json()
                                summary_data_list = summary.get('data', [])
                                for summary_data in summary_data_list:
                                    net_sales = summary_data.get('netSales', 0.0)
                                    payroll_taxes = summary_data.get('tax', 0.0)
                                    total_worked_hours = summary_data.get('hoursWorked', 0.0)
                                    
                                    record.write({
                                        'net_sales': net_sales,
                                        'total_worked_hours': total_worked_hours,
                                        'allowed_percentage_food_cost': 27,
                                        'last_updated_on_api': datetime.now(),
                                        'is_updated': True,
                                    })
                                    msg = f"Account THREE: Updated store {store_number} with Net Sales: {net_sales}, Tax: {payroll_taxes}, Hours: {total_worked_hours}"
                                    channel.message_post(body=msg)
                                    data_fetched = True

                            # Fetch Control Sheet
                            controlsheet_url = f"https://liveiqfranchiseeapi.subway.com/api/controlsheet/{store_number}/{end_date}"
                            controlsheet_response = requests.get(controlsheet_url, headers=HEADERS_ACCOUNT_THREE)
                            
                            if controlsheet_response.status_code == 200:
                                control = controlsheet_response.json()
                                control_data_list = control.get('data', [])
                                for control_data in control_data_list:
                                    summary = control_data.get('summary', {})
                                    productivity = summary.get('productivity')
                                    cashControl = control_data.get('cashControl', {})
                                    debit = cashControl.get('debit', {})
                                    debit_total = debit.get('total')
                                    
                                    record.write({
                                        'payroll_productivity': productivity,
                                        'paychex_total_debit': debit_total,
                                    })
                                    msg = f"Account THREE: Updated store {store_number} with Productivity: {productivity}, Debit Total: {debit_total}"
                                    channel.message_post(body=msg)

                            # Fetch Tips
                            tips_url = f"https://liveiqfranchiseeapi.subway.com/api/TipsDetails/{store_number}/startDate/{start_date}/endDate/{end_date}"
                            tips_response = requests.get(tips_url, headers=HEADERS_ACCOUNT_THREE)
                            
                            if tips_response.status_code == 200:
                                tips = tips_response.json()
                                tips_data_list = tips.get('data', [])
                                total_employee_split_tip = sum(tip_data.get('employeeSplitTip', 0.0) for tip_data in tips_data_list)
                                
                                record.write({'total_tips': total_employee_split_tip})
                                msg = f"Account THREE: Updated store {store_number} with Total Tips: {total_employee_split_tip}"
                                channel.message_post(body=msg)
                            
                except Exception as e:
                    _logger.exception(f"Error fetching data from Account THREE for store {store_number}")
                    channel.message_post(body=f"Exception (Account THREE) for store {store_number}: {str(e)}")

            if not data_fetched:
                msg = f"Store {store_number} not found in either Account TWO or Account THREE"
                channel.message_post(body=msg)
                _logger.warning(msg)


    def action_week_data(self):
        """
        Button action to update scheduling data for the current record(s)
        Uses self.week_starting_date, self.week_ending_date, and self.store_number
        """
        # Create/fetch channel for logging
        channel = self.env['discuss.channel'].sudo().search([('name', '=', 'Subway Scheduling Logs')], limit=1)
        if not channel:
            channel = self.env['discuss.channel'].sudo().create({
                "name": 'Subway Scheduling Logs',
                "channel_type": "channel",
                "channel_partner_ids": [(4, self.env.user.partner_id.id)],
            })

        # ============ GET API KEYS ============ #
        api_key_two = self.env['ir.config_parameter'].sudo().get_param('bsi_fetch_live_data.account_two_api_key')
        client_key_two = self.env['ir.config_parameter'].sudo().get_param('bsi_fetch_live_data.account_two_api_client')
        api_key_three = self.env['ir.config_parameter'].sudo().get_param('bsi_fetch_live_data.account_three_api_key')
        client_key_three = self.env['ir.config_parameter'].sudo().get_param('bsi_fetch_live_data.account_three_api_client')

        account_two_keys_missing = not api_key_two or not client_key_two
        account_three_keys_missing = not api_key_three or not client_key_three

        if account_two_keys_missing and account_three_keys_missing:
            msg = "Error: Missing API Key or Client Key for both Account TWO and Account THREE in system parameters."
            _logger.error(msg)
            channel.message_post(body=msg)
            raise UserError(msg)
        elif account_two_keys_missing:
            msg = "Error: Missing API Key or Client Key for Account TWO in system parameters."
            _logger.error(msg)
            channel.message_post(body=msg)
        elif account_three_keys_missing:
            msg = "Error: Missing API Key or Client Key for Account THREE in system parameters."
            _logger.error(msg)
            channel.message_post(body=msg)

        # Process each record in self (supports multi-record selection)
        for record in self:
            start_date = record.week_starting_date
            end_date = record.week_ending_date
            store_number = str(record.store_number) if record.store_number else None

            if not start_date or not end_date or not store_number:
                msg = f"Error: Missing required data for store {store_number or 'Unknown'}. Need week_starting_date, week_ending_date, and store_number."
                channel.message_post(body=msg)
                continue

            print(f"Processing Store: {store_number}, Start: {start_date}, End: {end_date}")

            # Try Account TWO first
            data_fetched = False
            
            if not account_two_keys_missing:
                HEADERS_ACCOUNT_TWO = {
                    "api-client": str(client_key_two),
                    "api-key": str(api_key_two)
                }

                try:
                    # Fetch restaurants to verify store exists in this account
                    res = requests.get("https://liveiqfranchiseeapi.subway.com/api/Restaurants", headers=HEADERS_ACCOUNT_TWO)
                    if res.status_code == 200:
                        restaurants = res.json()
                        store_exists = any(str(r.get('restaurantNumber')) == store_number for r in restaurants)
                        
                        if store_exists:
                            # Fetch Sales Summary
                            sales_url = f"https://liveiqfranchiseeapi.subway.com/api/SalesSummary/{store_number}/startDate/{start_date}/endDate/{end_date}"
                            sales_response = requests.get(sales_url, headers=HEADERS_ACCOUNT_TWO)
                            
                            if sales_response.status_code == 200:
                                summary = sales_response.json()
                                summary_data_list = summary.get('data', [])
                                for summary_data in summary_data_list:
                                    net_sales = summary_data.get('netSales', 0.0)
                                    payroll_taxes = summary_data.get('tax', 0.0)
                                    total_worked_hours = summary_data.get('hoursWorked', 0.0)
                                    
                                    record.write({
                                        'net_sales': net_sales,
                                        'total_worked_hours': total_worked_hours,
                                        'allowed_percentage_food_cost': 27,
                                        'last_updated_on_api': datetime.now(),
                                        'is_updated': True,
                                    })
                                    msg = f"Account TWO: Updated store {store_number} with Net Sales: {net_sales}, Tax: {payroll_taxes}, Hours: {total_worked_hours}"
                                    channel.message_post(body=msg)
                                    data_fetched = True

                            # Fetch Control Sheet
                            controlsheet_url = f"https://liveiqfranchiseeapi.subway.com/api/controlsheet/{store_number}/{end_date}"
                            controlsheet_response = requests.get(controlsheet_url, headers=HEADERS_ACCOUNT_TWO)
                            
                            if controlsheet_response.status_code == 200:
                                control = controlsheet_response.json()
                                control_data_list = control.get('data', [])
                                for control_data in control_data_list:
                                    summary = control_data.get('summary', {})
                                    productivity = summary.get('productivity')
                                    cashControl = control_data.get('cashControl', {})
                                    debit = cashControl.get('debit', {})
                                    debit_total = debit.get('total')
                                    
                                    record.write({
                                        'payroll_productivity': productivity,
                                        'paychex_total_debit': debit_total,
                                    })
                                    msg = f"Account TWO: Updated store {store_number} with Productivity: {productivity}, Debit Total: {debit_total}"
                                    channel.message_post(body=msg)

                            # Fetch Tips
                            tips_url = f"https://liveiqfranchiseeapi.subway.com/api/TipsDetails/{store_number}/startDate/{start_date}/endDate/{end_date}"
                            tips_response = requests.get(tips_url, headers=HEADERS_ACCOUNT_TWO)
                            
                            if tips_response.status_code == 200:
                                tips = tips_response.json()
                                tips_data_list = tips.get('data', [])
                                total_employee_split_tip = sum(tip_data.get('employeeSplitTip', 0.0) for tip_data in tips_data_list)
                                
                                record.write({'total_tips': total_employee_split_tip})
                                msg = f"Account TWO: Updated store {store_number} with Total Tips: {total_employee_split_tip}"
                                channel.message_post(body=msg)
                            
                except Exception as e:
                    _logger.exception(f"Error fetching data from Account TWO for store {store_number}")
                    channel.message_post(body=f"Exception (Account TWO) for store {store_number}: {str(e)}")

            # Try Account THREE if data not fetched from Account TWO
            if not data_fetched and not account_three_keys_missing:
                HEADERS_ACCOUNT_THREE = {
                    "api-client": str(client_key_three),
                    "api-key": str(api_key_three)
                }

                try:
                    # Fetch restaurants to verify store exists in this account
                    res = requests.get("https://liveiqfranchiseeapi.subway.com/api/Restaurants", headers=HEADERS_ACCOUNT_THREE)
                    if res.status_code == 200:
                        restaurants = res.json()
                        store_exists = any(str(r.get('restaurantNumber')) == store_number for r in restaurants)
                        
                        if store_exists:
                            # Fetch Sales Summary (Note: URL has 'end_date' instead of 'endDate' - using Account THREE pattern)
                            sales_url = f"https://liveiqfranchiseeapi.subway.com/api/SalesSummary/{store_number}/startDate/{start_date}/endDate/{end_date}"
                            sales_response = requests.get(sales_url, headers=HEADERS_ACCOUNT_THREE)
                            
                            if sales_response.status_code == 200:
                                summary = sales_response.json()
                                summary_data_list = summary.get('data', [])
                                for summary_data in summary_data_list:
                                    net_sales = summary_data.get('netSales', 0.0)
                                    payroll_taxes = summary_data.get('tax', 0.0)
                                    total_worked_hours = summary_data.get('hoursWorked', 0.0)
                                    
                                    record.write({
                                        'net_sales': net_sales,
                                        'total_worked_hours': total_worked_hours,
                                        'allowed_percentage_food_cost': 27,
                                        'last_updated_on_api': datetime.now(),
                                        'is_updated': True,
                                    })
                                    msg = f"Account THREE: Updated store {store_number} with Net Sales: {net_sales}, Tax: {payroll_taxes}, Hours: {total_worked_hours}"
                                    channel.message_post(body=msg)
                                    data_fetched = True

                            # Fetch Control Sheet
                            controlsheet_url = f"https://liveiqfranchiseeapi.subway.com/api/controlsheet/{store_number}/{end_date}"
                            controlsheet_response = requests.get(controlsheet_url, headers=HEADERS_ACCOUNT_THREE)
                            
                            if controlsheet_response.status_code == 200:
                                control = controlsheet_response.json()
                                control_data_list = control.get('data', [])
                                for control_data in control_data_list:
                                    summary = control_data.get('summary', {})
                                    productivity = summary.get('productivity')
                                    cashControl = control_data.get('cashControl', {})
                                    debit = cashControl.get('debit', {})
                                    debit_total = debit.get('total')
                                    
                                    record.write({
                                        'payroll_productivity': productivity,
                                        'paychex_total_debit': debit_total,
                                    })
                                    msg = f"Account THREE: Updated store {store_number} with Productivity: {productivity}, Debit Total: {debit_total}"
                                    channel.message_post(body=msg)

                            # Fetch Tips
                            tips_url = f"https://liveiqfranchiseeapi.subway.com/api/TipsDetails/{store_number}/startDate/{start_date}/endDate/{end_date}"
                            tips_response = requests.get(tips_url, headers=HEADERS_ACCOUNT_THREE)
                            
                            if tips_response.status_code == 200:
                                tips = tips_response.json()
                                tips_data_list = tips.get('data', [])
                                total_employee_split_tip = sum(tip_data.get('employeeSplitTip', 0.0) for tip_data in tips_data_list)
                                
                                record.write({'total_tips': total_employee_split_tip})
                                msg = f"Account THREE: Updated store {store_number} with Total Tips: {total_employee_split_tip}"
                                channel.message_post(body=msg)
                            
                except Exception as e:
                    _logger.exception(f"Error fetching data from Account THREE for store {store_number}")
                    channel.message_post(body=f"Exception (Account THREE) for store {store_number}: {str(e)}")

            if not data_fetched:
                msg = f"Store {store_number} not found in either Account TWO or Account THREE"
                channel.message_post(body=msg)
                _logger.warning(msg)

    # PP 19 NOV
    # ------------------Toast APIs---------------- #
    def action_week_sale_data(self):
        for record in self:
            record.ensure_one()

            # auth token
            auth_url = "https://ws-api.toasttab.com/authentication/v1/authentication/login"
            param = {
                'clientId': "QAJhsWiX2ndlZ6yFlOmBGPCXNEsytPSY",
                'clientSecret': "AZxR-VyWlIu_uoxoIe2ca8VluPUBsV1kgHi3-y1g8MOWiHqKUFV4CZ5mccMDjWnT",
                'userAccessType': 'TOAST_MACHINE_CLIENT',
            }
            responce = requests.post(auth_url, json=param)
            data = responce.json()
            print("----- data -------", data)
            access_token = data['token']['accessToken']

            # header
            headers = {
                'Authorization': f"Bearer {access_token}",
                'Toast-Restaurant-External-ID': "492a1017-21d9-4bcc-97ff-5ef458e0dbe0",
                'Content-Type': 'application/json'
            }

            start_dt = datetime.combine(record.week_starting_date, time(0, 0, 0))
            end_dt = datetime.combine(record.week_ending_date, time(23, 59, 59))
            current_dt = start_dt
            total_sale_amount = 0.0
            total_tips = 0.0
            pagesize = 100

            while current_dt <= end_dt:
                page = 1
                day_str = current_dt.strftime("%Y-%m-%d")
                start_iso = f"{day_str}T00:00:00.000Z"
                end_iso = f"{day_str}T23:59:59.999Z"
                print(f"\n Fetching orders for day: {day_str}")

                while True:
                    toast_url = (
                        "https://ws-api.toasttab.com/orders/v2/ordersBulk"
                        f"?startDate={start_iso}&endDate={end_iso}&pageSize={pagesize}&page={page}"
                    )

                    try:
                        sales_res = requests.get(toast_url, headers=headers)
                        if sales_res.status_code != 200:
                            print(f"Error: {sales_res.status_code}")
                            break

                        sale_data = sales_res.json()
                    except Exception as e:
                        print("API Error:", e)
                        break

                    if not sale_data: 
                        print("No more orders in this day.")
                        break

                    for order in sale_data:
                        for check in order.get("checks", []):
                            total_sale_amount += check.get("totalAmount", 0)
                            # print("-----total_sale_amount ------ ",total_sale_amount)
                            for payment in check.get("payments", []):
                                total_tips += payment.get("tipAmount", 0)
                                # print("------- total_tips------- ",total_tips)

                    if len(sale_data) < pagesize:
                        break
                    
                    page += 1  

                current_dt += timedelta(days=1)

            record.net_sales = total_sale_amount
            record.total_tips = total_tips

            print("\nFINAL TOTAL SALE AMOUNT:", total_sale_amount)
            print("FINAL TOTAL TIPS:", total_tips)     

    @api.model
    def update_subway_scheduling_data(self):
        print("_______self",self)
        channel = self.env['discuss.channel'].sudo().search([('name', '=', 'Subway Scheduling Logs')], limit=1)
        if not channel:
            channel = self.env['discuss.channel'].create({
                "name": 'Subway Scheduling Logs',
                "channel_type": "channel",
                "channel_partner_ids":[(4, self.env.user.partner_id.id)],
            })

        today = datetime.utcnow()
        day_distance = int(self.env['ir.config_parameter'].sudo().get_param('bsi_fetch_live_data.day_distance'))
        days_since_anchor = (today.weekday() - day_distance) % 7
        this_week_anchor_date = today - timedelta(days=days_since_anchor)
        this_week_anchor_date = this_week_anchor_date.replace(hour=0, minute=0, second=0, microsecond=0)
        last_week_anchor_date = this_week_anchor_date - timedelta(days=7)

        start_date = last_week_anchor_date.date()
        print("_______start_date",start_date)
        end_date = (this_week_anchor_date - timedelta(days=1)).date()
        print("_______end_date",end_date)
       
        if not start_date or not end_date:
            channel.message_post(body="Error: Missing start_date or end_date.")
            return {"status": "error", "message": "Missing start_date or end_date"}

        scheduling_model = self.env['store.scheduling'].sudo().search([
            ('week_starting_date', '=', start_date),
            ('week_ending_date', '=', end_date)
        ])

        scheduling_store_numbers = list({
            str(rec.store_number) for rec in scheduling_model if rec.store_number
        })
        print("_____scheduling_store_numbers",scheduling_store_numbers)

        # ============ GET API KEYS ============ #
        api_key_two = self.env['ir.config_parameter'].sudo().get_param('bsi_fetch_live_data.account_two_api_key')
        client_key_two = self.env['ir.config_parameter'].sudo().get_param('bsi_fetch_live_data.account_two_api_client')
        api_key_three = self.env['ir.config_parameter'].sudo().get_param('bsi_fetch_live_data.account_three_api_key')
        client_key_three = self.env['ir.config_parameter'].sudo().get_param('bsi_fetch_live_data.account_three_api_client')

        account_two_keys_missing = not api_key_two or not client_key_two
        account_three_keys_missing = not api_key_three or not client_key_three

        if account_two_keys_missing and account_three_keys_missing:
            msg = "Error: Missing API Key or Client Key for both Account TWO and Account THREE in system parameters."
            _logger.error(msg)
            channel.message_post(body=msg)
            return {"status": "error", "message": msg}
        elif account_two_keys_missing:
            msg = "Error: Missing API Key or Client Key for Account TWO in system parameters."
            _logger.error(msg)
            channel.message_post(body=msg)
        elif account_three_keys_missing:
            msg = "Error: Missing API Key or Client Key for Account THREE in system parameters."
            _logger.error(msg)
            channel.message_post(body=msg)

        unmatched_store_numbers = scheduling_store_numbers[:]

        # ============ ACCOUNT TWO ============ #
        if not account_two_keys_missing:
            HEADERS_ACCOUNT_TWO = {
                "api-client": str(client_key_two),
                "api-key": str(api_key_two)
            }

            try:
                res = requests.get("https://liveiqfranchiseeapi.subway.com/api/Restaurants", headers=HEADERS_ACCOUNT_TWO)
                if res.status_code != 200:
                    msg = f"Account TWO: Failed to fetch restaurants: {res.text}"
                    _logger.error(msg)
                    channel.message_post(body=msg)
                    return {"status": "error", "message": "Restaurant API failed", "response": res.text}
                restaurants = res.json()
            except Exception as e:
                _logger.exception("Exception in fetching restaurants (Account TWO)")
                channel.message_post(body=f"Exception fetching restaurants (Account TWO): {str(e)}")
                return {"status": "error", "message": f"Restaurant API error: {str(e)}"}

            matched_restaurants_account_two = [
                str(restaurant.get('restaurantNumber'))
                for restaurant in restaurants
                if restaurant.get('restaurantNumber') in scheduling_store_numbers
            ]

            unmatched_store_numbers = [
                sn for sn in unmatched_store_numbers if sn not in matched_restaurants_account_two
            ]

            if matched_restaurants_account_two:
                for chunk in self.chunk_list(matched_restaurants_account_two, 19):
                    restaurant_ids_string = ",".join(chunk)
                    sales_url = (
                        f"https://liveiqfranchiseeapi.subway.com/api/SalesSummary/"
                        f"{restaurant_ids_string}/startDate/{start_date}/endDate/{end_date}"
                    )
                    controlsheet = (
                        f"https://liveiqfranchiseeapi.subway.com/api/controlsheet/"
                        f"{restaurant_ids_string}/{end_date}"
                    )
                    try:
                        sales_response = requests.get(sales_url, headers=HEADERS_ACCOUNT_TWO)
                        if sales_response.status_code == 200:
                            summary = sales_response.json()
                            summary_data_list = summary.get('data', [])
                            for summary_data in summary_data_list:
                                restaurant_id = str(summary_data.get('resturantNumber'))
                                net_sales = summary_data.get('netSales', 0.0)
                                payroll_taxes = summary_data.get('tax', 0.0)
                                total_worked_hours = summary_data.get('hoursWorked', 0.0)
                                matched_records = scheduling_model.filtered(
                                    lambda rec: str(rec.store_number) == restaurant_id
                                )
                                for rec in matched_records:
                                    rec.write({
                                        'net_sales': net_sales,
                                        'total_worked_hours': total_worked_hours,
                                        'allowed_percentage_food_cost':27,
                                        'last_updated_on_api': datetime.now(),
                                        'is_updated': True,
                                    })
                                    msg = (
                                        f"Account TWO: Updated store {restaurant_id} with "
                                        f"Net Sales: {net_sales}, Tax: {payroll_taxes}, Hours: {total_worked_hours}"
                                    )
                                    channel.message_post(body=msg)
                        else:
                            msg = f"Account TWO: Failed to get sales data. Status: {sales_response.status_code}"
                            _logger.warning(msg)
                            channel.message_post(body=msg)

                        controlsheet_response = requests.get(controlsheet, headers=HEADERS_ACCOUNT_TWO)
                        if controlsheet_response.status_code == 200:
                            control = controlsheet_response.json()
                            control_data_list = control.get('data', [])
                            for control_data in control_data_list:
                                summary = control_data.get('summary', {})
                                productivity = summary.get('productivity')
                                restaurant_id = summary.get('storeNumber')
                                print("Productivity::::::::::::::::::", productivity)
                                cashControl = control_data.get('cashControl', {})
                                debit = cashControl.get('debit')
                                debit_total = debit.get('total')
                                matched_records = scheduling_model.filtered(
                                    lambda rec: str(rec.store_number) == restaurant_id and rec.week_ending_date == end_date
                                )
                                for rec in matched_records:
                                    rec.write({
                                        'payroll_productivity': productivity,
                                        'paychex_total_debit': debit_total,
                                    })
                                    msg = (
                                        f"Account TWO: Updated store {restaurant_id} with "
                                        f"Productivity: {productivity}, Hours: {debit_total}"
                                    )
                                    channel.message_post(body=msg)
                        else:
                            msg = f"Account TWO: Failed to get sales data. Status: {sales_response.status_code}"
                            _logger.warning(msg)
                            channel.message_post(body=msg)


                        # --- Call Tips API one by one ---
                        for rest_id in chunk:
                            tips_url = (
                                f"https://liveiqfranchiseeapi.subway.com/api/TipsDetails/"
                                f"{rest_id}/startDate/{start_date}/endDate/{end_date}"
                            )
                            tips_response = requests.get(tips_url, headers=HEADERS_ACCOUNT_TWO)
                            print("_________tips_response++++++", tips_response)
                            if tips_response.status_code == 200:
                                tips = tips_response.json()
                                tips_data_list = tips.get('data', [])
                                total_employee_split_tip = 0.0
                                for tip_data in tips_data_list:
                                    restaurant_id = str(tip_data.get('restaurantNumber'))
                                    employeeSplitTip = tip_data.get('employeeSplitTip', 0.0)
                                    total_employee_split_tip += employeeSplitTip
                                    print("________employeeSplitTip",employeeSplitTip, restaurant_id)
                                    matched_records = scheduling_model.filtered(
                                        lambda rec: str(rec.store_number) == restaurant_id
                                    )
                                    for rec in matched_records:
                                        rec.write({
                                            'total_tips': total_employee_split_tip,
                                        })
                                        msg = (
                                            f"Account TWO: Updated store {restaurant_id} with "
                                            f"Total Tips: {total_employee_split_tip}"
                                        )
                                        channel.message_post(body=msg)
                            else:
                                msg = f"Account TWO: Failed to get Tips data for {rest_id}. Status: {tips_response.status_code}"
                                _logger.warning(msg)
                                channel.message_post(body=msg)
                    except Exception as e:
                        _logger.exception("Sales API call failed (Account TWO)")
                        channel.message_post(body=f"Exception in sales API call (Account TWO): {str(e)}")
            else:
                channel.message_post(body="No matching restaurants found in Account TWO.")

        # ============ ACCOUNT THREE ============ #
        if not account_three_keys_missing:
            HEADERS_ACCOUNT_THREE = {
                "api-client": str(client_key_three),
                "api-key": str(api_key_three)
            }

            try:
                res = requests.get("https://liveiqfranchiseeapi.subway.com/api/Restaurants", headers=HEADERS_ACCOUNT_THREE)
                if res.status_code != 200:
                    msg = f"Account THREE: Failed to fetch restaurants: {res.text}"
                    _logger.error(msg)
                    channel.message_post(body=msg)
                    return {"status": "error", "message": "Restaurant API failed", "response": res.text}
                restaurants = res.json()
            except Exception as e:
                _logger.exception("Exception in fetching restaurants (Account THREE)")
                channel.message_post(body=f"Exception fetching restaurants (Account THREE): {str(e)}")
                return {"status": "error", "message": f"Restaurant API error: {str(e)}"}

            matched_restaurants_account_three = [
                str(restaurant.get('restaurantNumber'))
                for restaurant in restaurants
                if restaurant.get('restaurantNumber') in unmatched_store_numbers
            ]

            unmatched_store_numbers = [
                sn for sn in unmatched_store_numbers if sn not in matched_restaurants_account_three
            ]

            if matched_restaurants_account_three:
                for chunk in self.chunk_list(matched_restaurants_account_three, 19):
                    restaurant_ids_string = ",".join(chunk)
                    sales_url = (
                        f"https://liveiqfranchiseeapi.subway.com/api/SalesSummary/"
                        f"{restaurant_ids_string}/startDate/{start_date}/end_date/{end_date}"
                    )
                    controlsheet = (
                        f"https://liveiqfranchiseeapi.subway.com/api/controlsheet/"
                        f"{restaurant_ids_string}/{end_date}"
                    )
                    try:
                        sales_response = requests.get(sales_url, headers=HEADERS_ACCOUNT_THREE)
                        if sales_response.status_code == 200:
                            summary = sales_response.json()
                            summary_data_list = summary.get('data', [])
                            for summary_data in summary_data_list:
                                restaurant_id = str(summary_data.get('resturantNumber'))
                                net_sales = summary_data.get('netSales', 0.0)
                                payroll_taxes = summary_data.get('tax', 0.0)
                                total_worked_hours = summary_data.get('hoursWorked', 0.0)
                                matched_records = scheduling_model.filtered(
                                    lambda rec: str(rec.store_number) == restaurant_id
                                )
                                for rec in matched_records:
                                    rec.write({
                                        'net_sales': net_sales,
                                        'total_worked_hours': total_worked_hours,
                                        'allowed_percentage_food_cost':27,
                                        'last_updated_on_api': datetime.now(),
                                        'is_updated': True,
                                    })
                                    msg = (
                                        f"Account THREE: Updated store {restaurant_id} with "
                                        f"Net Sales: {net_sales}, Tax: {payroll_taxes}, Hours: {total_worked_hours}"
                                    )
                                    channel.message_post(body=msg)
                        else:
                            msg = f"Account THREE: Failed to get sales data. Status: {sales_response.status_code}"
                            _logger.warning(msg)
                            channel.message_post(body=msg)

                        controlsheet_response = requests.get(controlsheet, headers=HEADERS_ACCOUNT_TWO)
                        if controlsheet_response.status_code == 200:
                            control = controlsheet_response.json()
                            control_data_list = control.get('data', [])
                            for control_data in control_data_list:
                                summary = control_data.get('summary', {})
                                productivity = summary.get('productivity')
                                restaurant_id = summary.get('storeNumber')
                                print("Productivity::::::::::::::::::", productivity)
                                cashControl = control_data.get('cashControl', {})
                                debit = cashControl.get('debit')
                                debit_total = debit.get('total')
                                matched_records = scheduling_model.filtered(
                                    lambda rec: str(rec.store_number) == restaurant_id and rec.week_ending_date == end_date
                                )
                                for rec in matched_records:
                                    rec.write({
                                        'payroll_productivity': productivity,
                                        'paychex_total_debit': debit_total,
                                    })
                                    msg = (
                                        f"Account TWO: Updated store {restaurant_id} with "
                                        f"Productivity: {productivity}, Hours: {debit_total}"
                                    )
                                    channel.message_post(body=msg)
                        else:
                            msg = f"Account TWO: Failed to get sales data. Status: {sales_response.status_code}"
                            _logger.warning(msg)
                            channel.message_post(body=msg)

                        # --- Call Tips API one by one ---
                        for rest_id in chunk:
                            tips_url = (
                                f"https://liveiqfranchiseeapi.subway.com/api/TipsDetails/"
                                f"{rest_id}/startDate/{start_date}/endDate/{end_date}"
                            )
                            tips_response = requests.get(tips_url, headers=HEADERS_ACCOUNT_THREE)
                            if tips_response.status_code == 200:
                                tips = tips_response.json()
                                tips_data_list = tips.get('data', [])
                                total_employee_split_tip = 0.0
                                for tip_data in tips_data_list:
                                    restaurant_id = str(tip_data.get('resturantNumber'))
                                    employeeSplitTip = tip_data.get('employeeSplitTip', 0.0)
                                    total_employee_split_tip += employeeSplitTip
                                    matched_records = scheduling_model.filtered(
                                        lambda rec: str(rec.store_number) == restaurant_id
                                    )
                                    for rec in matched_records:
                                        rec.write({
                                            'total_tips': total_employee_split_tip,
                                        })
                                        msg = (
                                            f"Account THREE: Updated store {restaurant_id} with "
                                            f"Total Tips: {total_employee_split_tip}"
                                        )
                                        channel.message_post(body=msg)
                            else:
                                msg = f"Account THREE: Failed to get Tips data for {rest_id}. Status: {tips_response.status_code}"
                                _logger.warning(msg)
                                channel.message_post(body=msg)
                    except Exception as e:
                        _logger.exception("Sales API call failed (Account THREE)")
                        channel.message_post(body=f"Exception in sales API call (Account THREE): {str(e)}")
            else:
                channel.message_post(body="No matching restaurants found in Account THREE.")

            if unmatched_store_numbers:
                msg = f"Unmatched Store Numbers in BOTH Account TWO & THREE: {', '.join(unmatched_store_numbers)}"
                channel.message_post(body=msg)
