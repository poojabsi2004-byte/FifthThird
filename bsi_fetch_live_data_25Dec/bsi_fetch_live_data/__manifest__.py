# -*- coding: utf-8 -*-
{
    "name": "Subway Fetch Live Data",
    "author": "Botspot Infoware Pvt. Ltd.",
    "category": "Subway",
    "summary": """ Subway Fetch Live Data """,
    "website": "https://www.botspotinfoware.com",
    "version": "18.0.1.0",
    "description": """ Subway Fetch Live Data """,
    "depends": ['base','bsi_subway_base'],
    "data": [
        "security/ir.model.access.csv",
        "data/cron.xml",
        "views/res_config_settings.xml",
        "views/store_scheduling_view.xml",
    ],

    "license": "OPL-1",
    "installable": True,
    "application": True,
    "auto_install": False,
}
