# -*- coding: utf-8 -*-
"""
Facade for the modular database package.
"""

from .connection import (
    get_connection,
    get_connection_context,
    close_all_connections,
    init_db_for_profile
)
from .settings_repository import (
    ENCRYPTED_SETTINGS,
    get_setting,
    set_setting,
    add_to_blacklist,
    is_blacklisted,
    get_blacklist,
    remove_from_blacklist
)
from .lead_repository import (
    LEADS_SUMMARY_COLUMNS,
    add_lead,
    get_leads,
    get_leads_summary,
    count_leads,
    get_lead_by_id,
    update_lead_score,
    get_leads_by_score,
    delete_sent_leads,
    get_wyslano_emails,
    get_excluded_emails,
    mark_sent,
    mark_invalid,
    get_unscored_leads,
    get_scanned_domains,
    mark_domains_scanned
)
from .campaign_repository import (
    log_wysylka,
    count_sent_today,
    count_warmup_today,
    count_sent_last_hour,
    get_searched_combos,
    mark_combo_searched,
    clear_searched_combos,
    get_profile_names,
    get_profile,
    save_profile,
    delete_profile_from_db,
    get_history,
    clear_old_logs
)
from .smtp_repository import (
    save_smtp_accounts,
    get_smtp_accounts,
    set_main_account
)
from .sequence_repository import (
    get_sequences,
    get_sequence,
    add_sequence,
    delete_sequence,
    start_lead_sequence,
    get_pending_sequence_steps,
    mark_step_done,
    mark_as_responded
)
from .warmup_repository import (
    get_warmup_targets,
    add_warmup_target,
    delete_warmup_target
)
