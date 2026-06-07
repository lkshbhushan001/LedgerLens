"""Tests for JWT security and RBAC logic."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.security import create_access_token, require_user
from app.models.schemas import RBACMetadata, UserIdentity


class TestRBACMetadata:
    def test_roles_normalised(self) -> None:
        rbac = RBACMetadata(
            allowed_roles=["  ADMIN ", "Analyst"],
            document_id="doc-1",
            source_filename="report.pdf",
            uploaded_by="user-1",
            doc_type="pdf",
        )
        assert rbac.allowed_roles == ["admin", "analyst"]

    def test_empty_roles_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RBACMetadata(
                allowed_roles=[],
                document_id="doc-1",
                source_filename="report.pdf",
                uploaded_by="user-1",
                doc_type="pdf",
            )


class TestUserIdentity:
    def test_admin_bypass(self) -> None:
        admin = UserIdentity(user_id="u1", email="a@x.com", permission_groups=["read"], is_admin=True)
        rbac = RBACMetadata(
            allowed_roles=["restricted"],
            document_id="d1",
            source_filename="x.pdf",
            uploaded_by="u2",
            doc_type="pdf",
        )
        assert admin.can_access(rbac)

    def test_permitted_via_intersection(self) -> None:
        user = UserIdentity(user_id="u1", email="a@x.com", permission_groups=["fund-a", "analyst"])
        rbac = RBACMetadata(
            allowed_roles=["analyst"],
            document_id="d1",
            source_filename="x.pdf",
            uploaded_by="u2",
            doc_type="pdf",
        )
        assert user.can_access(rbac)

    def test_denied_no_intersection(self) -> None:
        user = UserIdentity(user_id="u1", email="a@x.com", permission_groups=["fund-b"])
        rbac = RBACMetadata(
            allowed_roles=["fund-a"],
            document_id="d1",
            source_filename="x.pdf",
            uploaded_by="u2",
            doc_type="pdf",
        )
        assert not user.can_access(rbac)


class TestTokenLifecycle:
    def test_encode_decode_roundtrip(self) -> None:
        token = create_access_token("u1", "a@x.com", ["analyst"])
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # header.payload.signature
