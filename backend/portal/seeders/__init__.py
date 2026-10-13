import logging

logger = logging.getLogger('cardvault.seeders')


def run_all_seeders():
    from .seed_roles import seed_roles
    from .seed_admin import seed_admin
    from .seed_customersupport import seed_customer_support
    from .seed_card_networks import seed_card_networks
    from .seed_card_issuers import seed_card_issuers
    from .seed_admin_settings import seed_admin_settings

    logger.info(f'[seed] roles: {seed_roles()} added')
    logger.info(f'[seed] admins (seed_admin.py): {seed_admin()}')
    logger.info(f'[seed] customer support (seed_customersupport.py): {seed_customer_support()}')
    logger.info(f'[seed] card_networks: {seed_card_networks()} added')
    logger.info(f'[seed] card_issuers: {seed_card_issuers()} added')
    logger.info(f'[seed] admin_settings: {seed_admin_settings()} added')
