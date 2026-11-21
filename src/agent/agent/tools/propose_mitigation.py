"""propose_mitigation: the agent's only write action. It records a PROPOSED mitigation in Lakebase
(decisions.mitigation_action) for a human approver; it can never approve. The row is written by the agent's
service principal on behalf of the requesting user: app.user is set to that user, so Postgres RLS only
lets the agent propose for regions the user is entitled to, and the audit trigger records both names.
"""

import os
from collections.abc import Callable

import psycopg
from agents import FunctionTool, function_tool
from databricks.sdk import WorkspaceClient

ENDPOINT = os.getenv("LAKEBASE_ENDPOINT", "projects/shortage-radar/branches/production/endpoints/primary")
ACTION_TYPES = ("REALLOCATE_INVENTORY", "EXPEDITE_ALTERNATE_SOURCE", "QUALIFY_ALTERNATE_SOURCE",
                "ALLOCATE_DEMAND", "FDA_506C_NOTIFICATION")


def _requesting_user(client_for: Callable[[str], WorkspaceClient] | None) -> str:
    if client_for is None:
        return os.getenv("RADAR_LOCAL_USER", "local-developer")
    return client_for("user").current_user.me().user_name


def _connect(app: WorkspaceClient) -> psycopg.Connection:
    cred = app.postgres.generate_database_credential(endpoint=ENDPOINT)
    host = app.postgres.get_endpoint(name=ENDPOINT).status.hosts.host
    user = app.config.client_id or app.current_user.me().user_name
    return psycopg.connect(host=host, dbname="databricks_postgres", user=user, password=cred.token,
                           sslmode="require", autocommit=True)


def make_propose_mitigation(client_for: Callable[[str], WorkspaceClient] | None) -> FunctionTool:
    @function_tool
    def propose_mitigation(disruption_id: str, sku_id: str, region: str, action_type: str,
                           description: str, est_revenue_protected: float | None = None) -> str:
        """Propose a mitigation for one SKU in an active disruption. It is saved as PROPOSED for a human
        to approve or reject in the shortage radar app; it is never approved by the agent.

        Args:
            disruption_id: disruption_id from the Supply Exposure agent (vendor id and event date).
            sku_id: affected SKU.
            region: US, EU or APAC.
            action_type: one of REALLOCATE_INVENTORY, EXPEDITE_ALTERNATE_SOURCE, QUALIFY_ALTERNATE_SOURCE,
                ALLOCATE_DEMAND, FDA_506C_NOTIFICATION.
            description: what to do and why, citing the numbers you used.
            est_revenue_protected: estimated revenue protected in USD, if known.
        """
        if action_type not in ACTION_TYPES:
            return f"Rejected: action_type must be one of {', '.join(ACTION_TYPES)}."
        user = _requesting_user(client_for)
        app = client_for("app") if client_for else WorkspaceClient()
        with _connect(app) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.user', %s, false)", (user,))
            try:
                cur.execute(
                    """INSERT INTO decisions.mitigation_action (disruption_id, sku_id, region, action_type, description,
                         est_revenue_protected, proposed_by, proposed_source, on_behalf_of)
                       VALUES (%s, %s, %s, %s, %s, %s, 'agent:radar-router', 'AGENT', %s) RETURNING action_id""",
                    (disruption_id, sku_id, region, action_type, description, est_revenue_protected, user))
            except psycopg.errors.InsufficientPrivilege:
                return f"Not saved: {user} is not entitled to propose actions for region {region}."
            action_id = cur.fetchone()[0]
        return f"Saved as PROPOSED action {action_id} for {sku_id} ({region}). A supply executive must approve it in the app."

    return propose_mitigation
