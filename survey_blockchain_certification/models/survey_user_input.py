import logging
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError

from ..utils import CONTRACT_ABI

_logger = logging.getLogger(__name__)

try:
    import warnings
    with warnings.catch_warnings():
        # Silencia la advertencia de depreciación de 'websockets' usada por 'web3'
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

    # Agregado para soportar la lógica de vista 'invisible="not certification"'
    certification = fields.Boolean(related='survey_id.certification', string='Certification', readonly=True)

    def _mark_done(self):
        """ Sobrescribe para activar el registro en blockchain al aprobar la certificación """
        res = super(SurveyUserInput, self)._mark_done()
        for user_input in self:
            if user_input.scoring_success and user_input.survey_id.certification:
                # Solo intentamos si no está ya registrado
                if user_input.blockchain_status != 'done':
                    user_input._register_on_blockchain()
        return res

    def action_retry_blockchain_registration(self):
        """ Acción para el botón de reintento manual """
        self.ensure_one()
        if self.blockchain_status == 'done':
            raise UserError(_("This certificate is already registered on the blockchain."))
        self._register_on_blockchain()

    def _register_on_blockchain(self):
        """ Lógica principal para interactuar con el Contrato Inteligente de Ethereum """
        if not Web3:
            self.write({
                'blockchain_status': 'error',
                'blockchain_error_msg': "Web3 python library is not installed."
            })
            return

        # 1. Obtener Credenciales
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
            # 2. Inicializar Web3
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            if not w3.is_connected():
                raise Exception(f"Could not connect to RPC URL: {rpc_url}")

            # 3. Instanciar Contrato
            # Usar dirección checksum es más seguro
            checksum_address = Web3.to_checksum_address(contract_address)
            contract = w3.eth.contract(address=checksum_address, abi=CONTRACT_ABI)

            # 4. Preparar Datos de la Transacción
            student_name = self.partner_id.name or self.email or "Unknown"
            course_name = self.survey_id.title or "Unknown Course"
            
            # Configuración de la cuenta
            account = w3.eth.account.from_key(private_key)
            nonce = w3.eth.get_transaction_count(account.address)
            chain_id = w3.eth.chain_id

            # Construir la transacción
            # Nota: issueCertificate acepta (string _studentName, string _courseName)
            txn = contract.functions.issueCertificate(
                student_name,
                course_name
            ).build_transaction({
                'chainId': chain_id,
                'gas': gas_limit,
                'gasPrice': w3.eth.gas_price,
                'nonce': nonce,
            })

            # 5. Firmar Transacción
            signed_txn = w3.eth.account.sign_transaction(txn, private_key=private_key)

            # 6. Enviar Transacción
            tx_hash_bytes = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            tx_hash = w3.to_hex(tx_hash_bytes)

            # Registrar paso inicial (Tx enviada)
            self.write({
                'blockchain_tx_hash': tx_hash,
                'blockchain_status': 'pending', 
                'blockchain_error_msg': False
            })
            
            # ¿Confirmar aquí si es posible para guardar hash? 
            # Odoo envuelve 'mark_done' en una transacción. Si esperamos, bloqueamos la UI.
            # Pero el requerimiento implica espera síncrona "Esperar el recibo para confirmar éxito".
            # Así que esperamos.
            
            # 7. Esperar el Recibo
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash_bytes)

            if receipt['status'] == 0:
                raise Exception("Transaction failed (reverted on chain).")

            # 8. Analizar Logs
            # Buscamos el evento CertificateIssued
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
            # Explícitamente NO lanzamos la excepción a Odoo para evitar rollback del estado 'done' de la encuesta.
