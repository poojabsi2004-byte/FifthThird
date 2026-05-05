from odoo import fields, models, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sftp_username = fields.Char(string='SFTP Username', config_parameter='bsi_bank_connection.sftp_username', store=True, nolabel=False)
    sftp_password = fields.Char(string='SFTP Password', config_parameter='bsi_bank_connection.sftp_password', store=True, nolabel=False)
    # sftp_name = fields.Char(string='SFTP Name', store=True)
    # sftp_host = fields.Char(string='SFTP Host', store=True)
    # sftp_port = fields.Integer(string='SFTP Port', store=True)