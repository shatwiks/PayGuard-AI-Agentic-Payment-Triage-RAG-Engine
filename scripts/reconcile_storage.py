"""Storage Reconciliation and Orphaned File Detection Utility.

Audits ./storage/uploads against database KnowledgeDocument records.
Identifies:
1. Valid Active Files: Referenced by active KnowledgeDocument in database.
2. Inactive Files: Referenced by soft-deleted KnowledgeDocument.
3. Orphaned Files: Present on disk but no longer referenced in database.
4. Missing Files: Referenced in database but missing from disk.

Safe by default (dry-run). Never deletes unless --purge is explicitly passed.
"""

import argparse
import asyncio
import os
import sys
from typing import Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.config import settings
from backend.app.models.knowledge import KnowledgeDocument


async def audit_storage(db_url: str, purge: bool = False):
    print("================================================================================")
    print("PAYGUARD AI: DOCUMENT STORAGE RECONCILIATION AUDIT")
    print("================================================================================")
    print(f"Storage Directory: {os.path.abspath(settings.UPLOAD_STORAGE_DIR)}")
    print(f"Database Target:   {db_url.split('@')[-1] if '@' in db_url else db_url}")
    print(f"Purge Mode:        {'PURGE ENABLED (Destructive)' if purge else 'DRY RUN (Safe / Read-Only)'}")
    print("--------------------------------------------------------------------------------")

    if not os.path.exists(settings.UPLOAD_STORAGE_DIR):
        print(f"Storage directory '{settings.UPLOAD_STORAGE_DIR}' does not exist.")
        return

    # 1. Discover all disk files
    disk_files = set()
    for root, _, files in os.walk(settings.UPLOAD_STORAGE_DIR):
        for f in files:
            if f in (".gitkeep", ".pending_deletes"):
                continue
            full_path = os.path.normpath(os.path.abspath(os.path.join(root, f)))
            disk_files.add(full_path)

    print(f"Found {len(disk_files)} non-gitkeep file(s) on disk.")

    # 2. Query all database document storage paths
    engine = create_async_engine(db_url, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    active_paths: Set[str] = set()
    inactive_paths: Set[str] = set()

    async with session_maker() as session:
        stmt = select(KnowledgeDocument.id, KnowledgeDocument.storage_path, KnowledgeDocument.is_active)
        res = await session.execute(stmt)
        rows = res.all()

        for doc_id, storage_path, is_active in rows:
            if storage_path:
                norm = os.path.normpath(os.path.abspath(storage_path))
                if is_active:
                    active_paths.add(norm)
                else:
                    inactive_paths.add(norm)

    await engine.dispose()

    print(f"Found {len(active_paths)} active document storage path(s) in DB.")
    print(f"Found {len(inactive_paths)} inactive document storage path(s) in DB.")
    print("--------------------------------------------------------------------------------")

    # 3. Categorize disk files
    matched_active = disk_files.intersection(active_paths)
    matched_inactive = disk_files.intersection(inactive_paths)
    orphaned_files = disk_files - (active_paths | inactive_paths)
    missing_active_files = active_paths - disk_files

    print(f"Active Files on Disk (Protected):    {len(matched_active)}")
    print(f"Inactive Files on Disk (Soft-deleted): {len(matched_inactive)}")
    print(f"Orphaned Files on Disk:              {len(orphaned_files)}")
    print(f"Missing Active Files:                {len(missing_active_files)}")

    if orphaned_files:
        print("\n[ORPHANED FILES ON DISK (Not in DB)]:")
        for p in sorted(orphaned_files):
            size_kb = os.path.getsize(p) / 1024
            print(f"  * {os.path.basename(p)} ({size_kb:.1f} KB)")

    if missing_active_files:
        print("\n[WARNING: MISSING ACTIVE FILES (In DB but missing on disk)]:")
        for p in sorted(missing_active_files):
            print(f"  ! {p}")

    # 4. Handle purge if explicitly requested
    if purge and orphaned_files:
        print("\nPurging orphaned files...")
        purged = 0
        for p in orphaned_files:
            try:
                os.remove(p)
                purged += 1
                print(f"  - Removed: {os.path.basename(p)}")
            except Exception as e:
                print(f"  ! Failed to remove {p}: {e}")
        print(f"Purge complete: {purged} file(s) removed.")
    elif not purge and orphaned_files:
        print("\nDry run completed. Run with --purge to remove orphaned files.")

    print("================================================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconcile uploaded file storage with database records.")
    parser.add_argument("--purge", action="store_true", help="Delete orphaned files not referenced by any database record.")
    parser.add_argument("--db-url", type=str, default=settings.DATABASE_URL, help="Database connection URL.")
    args = parser.parse_args()

    asyncio.run(audit_storage(db_url=args.db_url, purge=args.purge))
