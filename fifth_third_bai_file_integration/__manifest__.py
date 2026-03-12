{
    'name': 'BAI File Import',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Upload and parse BAI files',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/bai_import_view.xml',
        'views/bai_transaction_view.xml',
        'views/bai_groups.xml',
        'views/bai_groups_accounts.xml',
        'data/ir_cron.xml',
    ],
    'installable': True,
}
