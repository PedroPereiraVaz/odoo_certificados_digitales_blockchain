{
    'name': 'Blockchain Certification for Surveys',
    'version': '18.0.1.0.0',
    'category': 'Marketing/Surveys',
    'summary': 'Issue Ethereum certificates for passing surveys/courses',
    'description': """
        Integrates Odoo with an Ethereum Smart Contract to issue academic certificates.
        Features:
        - Auto-issue certificate on survey pass.
        - Store TX hash and Certificate ID.
        - Retry mechanism for failed transactions.
    """,
    'author': 'Pedro',
    'depends': ['base', 'survey'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/survey_user_input_views.xml',
    ],
    'external_dependencies': {
        'python': ['web3'],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
