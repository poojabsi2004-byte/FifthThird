# -*- coding: utf-8 -*-

from odoo import fields, models, api, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    account_two_api_key = fields.Char(string="API Key", config_parameter='bsi_fetch_live_data.account_two_api_key')
    account_two_api_client = fields.Char(string="Client Key", config_parameter='bsi_fetch_live_data.account_two_api_client')
    account_three_api_key = fields.Char(string="API Key", config_parameter='bsi_fetch_live_data.account_three_api_key')
    account_three_api_client = fields.Char(string="Client Key", config_parameter='bsi_fetch_live_data.account_three_api_client')
    day_distance = fields.Integer(string="Days Difference", config_parameter='bsi_fetch_live_data.day_distance')

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res['account_two_api_key'] = self.env['ir.config_parameter'].sudo().get_param(
            'bsi_fetch_live_data.account_two_api_key')
        res['account_two_api_client'] = self.env['ir.config_parameter'].sudo().get_param(
            'bsi_fetch_live_data.account_two_api_client')
        res['account_three_api_key'] = self.env['ir.config_parameter'].sudo().get_param(
            'bsi_fetch_live_data.account_three_api_key')
        res['account_three_api_client'] = self.env['ir.config_parameter'].sudo().get_param(
            'bsi_fetch_live_data.account_three_api_client')
        res['day_distance'] = self.env['ir.config_parameter'].sudo().get_param(
            'bsi_fetch_live_data.day_distance')
        return res

    def set_values(self):
        res = super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('bsi_fetch_live_data.account_two_api_key',
                                                         self.account_two_api_key)
        self.env['ir.config_parameter'].sudo().set_param('bsi_fetch_live_data.account_two_api_client',
                                                         self.account_two_api_client)
        self.env['ir.config_parameter'].sudo().set_param('bsi_fetch_live_data.account_three_api_key',
                                                         self.account_three_api_key)
        self.env['ir.config_parameter'].sudo().set_param('bsi_fetch_live_data.account_three_api_client',
                                                         self.account_three_api_client)
        self.env['ir.config_parameter'].sudo().set_param('bsi_fetch_live_data.day_distance',
                                                         self.day_distance)
        return res
