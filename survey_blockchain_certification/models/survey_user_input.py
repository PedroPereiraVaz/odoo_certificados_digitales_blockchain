import logging
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError

from ..utils import CONTRACT_ABI

_logger = logging.getLogger(__name__)

try:
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        from web3 import Web3
except ImportError:
    _logger.warning("Web3 library not found. Blockchain integration will not work.")
    Web3 = None


class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    blockchain_tx_hash = fields.Char(string='Transaction Hash', readonly=True, copy=False)
    blockchain_certificate_id = fields.Integer(string='Certificate ID', readonly=True, copy=False)
    blockchain_status = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Confirmed'),
        ('error', 'Error')
    ], string='Blockchain Status', default='pending', copy=False, readonly=True)
    blockchain_error_msg = fields.Text(string='Error Message', readonly=True, copy=False)

    # Added to support view logic 'invisible="not certification"'
    certification = fields.Boolean(related='survey_id.certification', string='Certification', readonly=True)

    def _mark_done(self):
        """ Override to trigger blockchain registration on certification success """
        res = super(SurveyUserInput, self)._mark_done()
        for user_input in self:
            if user_input.scoring_success and user_input.survey_id.certification:
                # We only attempt if it's not already done.
                if user_input.blockchain_status != 'done':
                    user_input._register_on_blockchain()
        return res

    def action_retry_blockchain_registration(self):
        """ Action for the manual retry button """
        self.ensure_one()
        if self.blockchain_status == 'done':
            raise UserError(_("This certificate is already registered on the blockchain."))
        self._register_on_blockchain()

    def _register_on_blockchain(self):
        """ Core logic to interact with Ethereum Smart Contract """
        if not Web3:
            self.write({
                'blockchain_status': 'error',
                'blockchain_error_msg': "Web3 python library is not installed."
            })
            return

        # 1. Get Credentials
        params = self.env['ir.config_parameter'].sudo()
        rpc_url = params.get_param('survey_blockchain_certification.blockchain_rpc_url')
        contract_address = params.get_param('survey_blockchain_certification.blockchain_contract_address')
        private_key = params.get_param('survey_blockchain_certification.blockchain_wallet_private_key')
        gas_limit = int(params.get_param('survey_blockchain_certification.blockchain_gas_limit', 200000))

        if not all([rpc_url, contract_address, private_key]):
            self.write({
                'blockchain_status': 'error',
                'blockchain_error_msg': "Blockchain configuration is missing (URL, Address or Private Key)."
            })
            return

        try:
            # 2. Initialize Web3
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            if not w3.is_connected():
                raise Exception(f"Could not connect to RPC URL: {rpc_url}")

            # 3. Instantiate Contract
            # Checksum address is safer
            checksum_address = Web3.to_checksum_address(contract_address)
            contract = w3.eth.contract(address=checksum_address, abi=CONTRACT_ABI)

            # 4. Prepare Transaction Data
            student_name = self.partner_id.name or self.email or "Unknown"
            course_name = self.survey_id.title or "Unknown Course"
            
            # Account setup
            account = w3.eth.account.from_key(private_key)
            nonce = w3.eth.get_transaction_count(account.address)
            chain_id = w3.eth.chain_id

            # Build transaction
            # Note: issueCertificate takes (string _studentName, string _courseName)
            txn = contract.functions.issueCertificate(
                student_name,
                course_name
            ).build_transaction({
                'chainId': chain_id,
                'gas': gas_limit,
                'gasPrice': w3.eth.gas_price,
                'nonce': nonce,
            })

            # 5. Sign Transaction
            signed_txn = w3.eth.account.sign_transaction(txn, private_key=private_key)

            # 6. Send Transaction
            tx_hash_bytes = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            tx_hash = w3.to_hex(tx_hash_bytes)

            # Log initial step (Tx sent)
            self.write({
                'blockchain_tx_hash': tx_hash,
                'blockchain_status': 'pending', 
                'blockchain_error_msg': False
            })
            
            # Commit here if possible to save hash? 
            # Odoo wraps 'mark_done' in a transaction. If we wait, we block the UI.
            # But the requirement implies synchronous waiting "Esperar el recibo to confirm success".
            # So we wait.
            
            # 7. Wait for Receipt
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash_bytes)

            if receipt['status'] == 0:
                raise Exception("Transaction failed (reverted on chain).")

            # 8. Parse Logs
            # We look for CertificateIssued event
            logs = contract.events.CertificateIssued().process_receipt(receipt)
            
            if logs:
                certificate_id = logs[0]['args']['certificateId']
                self.write({
                    'blockchain_certificate_id': certificate_id,
                    'blockchain_status': 'done',
                    'blockchain_error_msg': False
                })
            else:
                self.write({
                    'blockchain_status': 'error',
                    'blockchain_error_msg': "Transaction successful but no CertificateIssued event found."
                })

        except Exception as e:
            _logger.exception("Blockchain registration failed")
            self.write({
                'blockchain_status': 'error',
                'blockchain_error_msg': str(e)
            })
            # We explicitly do NOT raise the exception properly to Odoo to avoid rollback of the survey 'done' state.
