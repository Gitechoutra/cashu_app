def init_app(app):
    with app.app_context():
        from .roles import Roles, RoleName                            # noqa: F401
        from .users import Users, UserStatus                          # noqa: F401
        from .user_sessions import UserSessions, SessionStatus        # noqa: F401
        from .otp_verifications import OTPVerifications               # noqa: F401
        from .webauthn_credentials import WebAuthnCredentials         # noqa: F401
        from .audit_logs import AuditLogs                             # noqa: F401
        from .card_issuers import CardIssuers                         # noqa: F401
        from .financial_consents import FinancialConsents             # noqa: F401
        from .linked_cards import LinkedCards                         # noqa: F401
        from .card_data_snapshots import CardDataSnapshots            # noqa: F401
        from .card_link_sessions import CardLinkSessions              # noqa: F401
        from .card_transactions import CardTransactions               # noqa: F401
        from .bills import Bills                                      # noqa: F401
        from .payment_transactions import PaymentTransactions         # noqa: F401
        from .payment_gateways import PaymentGateways                 # noqa: F401
        from .support_tickets import SupportTickets                   # noqa: F401
        from .support_messages import SupportMessages                 # noqa: F401
        from .device_bindings import DeviceBindings                   # noqa: F401
        from .login_history import LoginHistory                       # noqa: F401
        from .notifications import Notifications                      # noqa: F401
        from .user_profiles import UserProfiles                       # noqa: F401
        from .user_security_settings import UserSecuritySettings      # noqa: F401
        from .admin_settings import AdminSettings                     # noqa: F401
        from .card_networks import CardNetworks                       # noqa: F401
        from .qr_payments import QrPayments                           # noqa: F401
        from .reconciliation import Reconciliation                    # noqa: F401
        from .transaction_errors import TransactionErrors             # noqa: F401
        from .kyc_verifications import KycVerifications               # noqa: F401
        from .bank_accounts import BankAccounts                       # noqa: F401

    app.logger.info('Initialized models')
