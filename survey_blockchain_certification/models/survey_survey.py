from odoo import models, fields

class Survey(models.Model):
    _inherit = 'survey.survey'

    blockchain_certification = fields.Boolean(
        string='Register on Blockchain',
        help="If checked, the certificate will be issued on the blockchain upon successful completion.",
        default=False
    )
