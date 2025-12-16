from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    blockchain_rpc_url = fields.Char(
        string='Blockchain RPC URL',
        config_parameter='survey_blockchain_certification.blockchain_rpc_url',
        help="E.g: http://127.0.0.1:8545 or https://polygon-rpc.com"
    )
    blockchain_contract_address = fields.Char(
        string='Contract Address',
        config_parameter='survey_blockchain_certification.blockchain_contract_address',
        help="The address of the deployed AcademicRegistry contract."
    )
    blockchain_wallet_private_key = fields.Char(
        string='Private Key',
        config_parameter='survey_blockchain_certification.blockchain_wallet_private_key',
        help="Private key of the university wallet to sign transactions.",
    )
    blockchain_gas_limit = fields.Integer(
        string='Gas Limit',
        config_parameter='survey_blockchain_certification.blockchain_gas_limit',
        default=200000
    )
