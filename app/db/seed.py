from __future__ import annotations

from sqlalchemy import func

from app.db.session import SessionLocal
from app.models.category import CategoryGroup, SubCategory
from app.models.metric import Metric
from app.models.role import DashboardScope, EntryScope, Role
from app.models.session_inv import InventorySession
from app.models.user import User
from loginpage import hash_password

DEFAULT_METRICS = ["ltr", "kg", "gm", "nos"]

VIEW_ROLE_NAME = "view"

DEFAULT_GROUPS = {
    "Raw Materials": ["Herbs", "Powders"],
    "Semi Finished Goods": ["Majun (Semi Finished)", "Roghan (Semi Finished)"],
    "Finished Goods": ["Majun", "Syrup (Semi Finished)", "Roghan"],
}


def seed() -> None:
    with SessionLocal() as db:
        admin_role = db.query(Role).filter(Role.name == "Admin").one_or_none()
        if not admin_role:
            admin_role = Role(
                name="Admin",
                can_view_dashboard=True,
                can_view_add_item=True,
                can_view_raw=True,
                can_view_sfg=True,
                can_view_fg=True,
                can_view_manage_data=True,
                can_view_users=True,
                can_manage_users=True,
                can_manage_roles=True,
                can_import_master_data=True,
                can_add_entry_raw=True,
                can_add_entry_sfg=True,
                can_add_entry_fg=True,
                can_edit_entry_raw=True,
                can_edit_entry_sfg=True,
                can_edit_entry_fg=True,
                can_edit_manage_data=True,
                can_edit_add_item=True,
                can_bulk_edit_delete_add_item=True,
                can_bulk_edit_delete_raw=True,
                can_bulk_edit_delete_sfg=True,
                can_bulk_edit_delete_fg=True,
                can_export_dashboard_summary=True,
                can_export_dashboard_entries=True,
                can_view_dashboard_cards=True,
                can_open_dashboard_modal=True,
                dashboard_scope=DashboardScope.ORG,
                entry_scope=EntryScope.ORG,
                add_item_scope=DashboardScope.ORG,
                raw_scope=EntryScope.ORG,
                sfg_scope=EntryScope.ORG,
                fg_scope=EntryScope.ORG,
            )
            db.add(admin_role)
            db.flush()
        else:
            admin_role.add_item_scope = DashboardScope.ORG
            admin_role.raw_scope = EntryScope.ORG
            admin_role.sfg_scope = EntryScope.ORG
            admin_role.fg_scope = EntryScope.ORG
            admin_role.can_edit_entry_raw = True
            admin_role.can_edit_entry_sfg = True
            admin_role.can_edit_entry_fg = True
            admin_role.can_edit_add_item = True

        view_role = (
            db.query(Role)
            .filter(func.lower(Role.name) == VIEW_ROLE_NAME)
            .one_or_none()
        )
        if not view_role:
            view_role = Role(
                name="View",
                can_view_dashboard=True,
                can_view_add_item=True,
                can_view_raw=True,
                can_view_sfg=True,
                can_view_fg=True,
                can_view_manage_data=True,
                can_view_users=True,
                can_manage_users=False,
                can_manage_roles=False,
                can_import_master_data=False,
                can_add_entry_raw=False,
                can_add_entry_sfg=False,
                can_add_entry_fg=False,
                can_edit_entry_raw=False,
                can_edit_entry_sfg=False,
                can_edit_entry_fg=False,
                can_edit_manage_data=False,
                can_edit_add_item=False,
                can_bulk_edit_delete_add_item=False,
                can_bulk_edit_delete_raw=False,
                can_bulk_edit_delete_sfg=False,
                can_bulk_edit_delete_fg=False,
                can_export_dashboard_summary=False,
                can_export_dashboard_entries=False,
                can_view_dashboard_cards=True,
                can_open_dashboard_modal=True,
                dashboard_scope=DashboardScope.ORG,
                entry_scope=EntryScope.ORG,
                add_item_scope=DashboardScope.ORG,
                raw_scope=EntryScope.ORG,
                sfg_scope=EntryScope.ORG,
                fg_scope=EntryScope.ORG,
            )
            db.add(view_role)
            db.flush()
        else:
            view_role.name = "View"
            view_role.can_view_dashboard = True
            view_role.can_view_add_item = True
            view_role.can_view_raw = True
            view_role.can_view_sfg = True
            view_role.can_view_fg = True
            view_role.can_view_manage_data = True
            view_role.can_view_users = True
            view_role.can_manage_users = False
            view_role.can_manage_roles = False
            view_role.can_import_master_data = False
            view_role.can_add_entry_raw = False
            view_role.can_add_entry_sfg = False
            view_role.can_add_entry_fg = False
            view_role.can_edit_entry_raw = False
            view_role.can_edit_entry_sfg = False
            view_role.can_edit_entry_fg = False
            view_role.can_edit_manage_data = False
            view_role.can_edit_add_item = False
            view_role.can_bulk_edit_delete_add_item = False
            view_role.can_bulk_edit_delete_raw = False
            view_role.can_bulk_edit_delete_sfg = False
            view_role.can_bulk_edit_delete_fg = False
            view_role.can_export_dashboard_summary = False
            view_role.can_export_dashboard_entries = False
            view_role.can_view_dashboard_cards = True
            view_role.can_open_dashboard_modal = True
            view_role.dashboard_scope = DashboardScope.ORG
            view_role.entry_scope = EntryScope.ORG
            view_role.add_item_scope = DashboardScope.ORG
            view_role.raw_scope = EntryScope.ORG
            view_role.sfg_scope = EntryScope.ORG
            view_role.fg_scope = EntryScope.ORG

        admin_user = db.query(User).filter(User.username == "Admin").one_or_none()
        if not admin_user:
            admin_user = User(
                name="Admin",
                username="Admin",
                password=hash_password("adminthegreat"),
                role_id=admin_role.id,
                parent_admin_id=None,
                dashboard_share_enabled=True,
            )
            db.add(admin_user)
        else:
            if admin_user.password == "adminthegreat":
                admin_user.password = hash_password("adminthegreat")
            admin_user.role_id = admin_role.id

        for metric in DEFAULT_METRICS:
            if not db.query(Metric).filter(Metric.name == metric).count():
                db.add(Metric(name=metric))

        for group_name, subs in DEFAULT_GROUPS.items():
            group = db.query(CategoryGroup).filter(CategoryGroup.name == group_name).one_or_none()
            if not group:
                group = CategoryGroup(name=group_name)
                db.add(group)
                db.flush()
            for sub in subs:
                exists = (
                    db.query(SubCategory)
                    .filter(SubCategory.group_id == group.id, SubCategory.name == sub)
                    .one_or_none()
                )
                if not exists:
                    db.add(SubCategory(name=sub, group_id=group.id))

        if not db.query(InventorySession).count():
            db.add(InventorySession(code="2025-09", name="Sep-2025 Monthly", status="active"))

        db.commit()


if __name__ == "__main__":
    seed()
