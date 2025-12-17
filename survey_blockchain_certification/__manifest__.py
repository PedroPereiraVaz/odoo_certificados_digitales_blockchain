{
    'name': 'Certificados digitales en Blockchain',
    'version': '18.0.1.0.0',
    'category': 'Marketing/Surveys',
    'summary': 'Emitir certificados en Ethereum al aprobar encuestas/cursos',
    'description': """
        Integra Odoo con un contrato inteligente (Smart Contract) de Ethereum para emitir certificados académicos.
        Características:
        - Emisión automática del certificado al aprobar una encuesta.
        - Almacenamiento del hash de la transacción (TX) y del ID del certificado.
        - Mecanismo de reintento para transacciones fallidas.
    """,
    'author': 'Pedro',
    'depends': ['base', 'survey'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/survey_survey_views.xml',
        'views/survey_user_input_views.xml',
    ],
    'external_dependencies': {
        'python': ['web3'],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
