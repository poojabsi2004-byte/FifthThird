{
    'name': 'BSI Bank Connection',
    'version': '1.0',
    'category': 'BSI Bank',
    'summary': 'Upload and parse BAI files',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/bai_transaction_view.xml',
        'views/bai_bank_files.xml',
        'views/bai_bank_groups.xml',
        'views/bai_bank_accounts.xml',
        'views/bai_bank_account_transaction.xml',
        'views/number_sequence.xml',
        'views/res_config_setting.xml',
        'data/ir.cron.xml',
    ],
    'installable': True,
}
