"""Tests for storage services and presigned URL operations."""

import uuid
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from app.config import Settings
from app.services.s3 import (
    MockStorageService,
    S3StorageService,
    get_storage_service,
)


def test_mock_storage_key_generation() -> None:
    storage = MockStorageService()
    user_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    media_id = str(uuid.uuid4())

    # Valid mp4, mov, webm (with or without leading dot, case insensitive)
    for ext in ("mp4", ".MOV", "webm"):
        key = storage.generate_object_key(user_id, project_id, media_id, ext)
        assert key.startswith(f"users/{user_id}/projects/{project_id}/media/{media_id}/")
        assert key.endswith(f".{ext.lstrip('.').lower()}")
        # Unpredictable token in path
        token = key.split("/")[-1].split(".")[0]
        assert len(token) == 32  # uuid4 hex length


def test_storage_key_generation_invalid_extension() -> None:
    storage = MockStorageService()
    user_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    media_id = str(uuid.uuid4())

    with pytest.raises(ValueError, match="Invalid or unsupported video extension"):
        storage.generate_object_key(user_id, project_id, media_id, "exe")

    with pytest.raises(ValueError, match="Invalid or unsupported video extension"):
        storage.generate_object_key(user_id, project_id, media_id, "")


def test_storage_key_generation_invalid_uuids() -> None:
    storage = MockStorageService()
    valid_uuid = str(uuid.uuid4())

    with pytest.raises(ValueError, match="must be valid UUIDs"):
        storage.generate_object_key("not-uuid", valid_uuid, valid_uuid, "mp4")

    with pytest.raises(ValueError, match="must be valid UUIDs"):
        storage.generate_object_key(valid_uuid, "../../traversal", valid_uuid, "mp4")


def test_mock_storage_presigned_upload() -> None:
    storage = MockStorageService(default_ttl=900)
    s3_key = "users/u1/projects/p1/media/m1/asset.mp4"
    res = storage.create_presigned_upload_url(s3_key, content_type="video/mp4", expires_in=600)

    assert res.s3_key == s3_key
    assert res.expires_in == 600
    assert "mock-s3.localhost" in res.upload_url
    assert "https://" in res.upload_url


def test_mock_storage_verify_object() -> None:
    storage = MockStorageService()
    s3_key = "users/u1/projects/p1/media/m1/asset.mp4"

    # Initially missing
    meta_before = storage.verify_object("nonexistent-key")
    assert meta_before.exists is False
    assert meta_before.size_bytes == 0

    # Set mock object
    storage.set_mock_object(s3_key, size_bytes=1048576, exists=True)
    meta_after = storage.verify_object(s3_key)
    assert meta_after.exists is True
    assert meta_after.size_bytes == 1048576
    assert meta_after.content_type == "video/mp4"


def test_mock_storage_download_url() -> None:
    storage = MockStorageService()
    s3_key = "users/u1/projects/p1/media/m1/asset.mp4"
    url = storage.create_presigned_download_url(s3_key, expires_in=300, filename="test.mp4")
    assert "mock-s3.localhost" in url
    assert s3_key in url


def test_mock_storage_delete_object() -> None:
    storage = MockStorageService()
    s3_key = "users/u1/projects/p1/media/m1/asset.mp4"
    storage.set_mock_object(s3_key, size_bytes=1000)

    assert storage.verify_object(s3_key).exists is True
    res = storage.delete_object(s3_key)
    assert res is True
    assert storage.verify_object(s3_key).exists is False
    # Idempotent re-delete
    assert storage.delete_object(s3_key) is True


def test_s3_storage_service_missing_bucket_raises() -> None:
    settings = Settings(AWS_S3_BUCKET="")
    with pytest.raises(ValueError, match="AWS_S3_BUCKET must be configured"):
        S3StorageService(settings)


def test_s3_storage_service_presigned_upload_mocked_client() -> None:
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = (
        "https://s3.ap-south-1.amazonaws.com/test-bucket/asset.mp4?sig=test"
    )

    settings = Settings(AWS_S3_BUCKET="test-bucket", AWS_REGION="ap-south-1")
    service = S3StorageService(settings, client=mock_client)

    s3_key = "users/u1/projects/p1/media/m1/token.mp4"
    res = service.create_presigned_upload_url(s3_key, content_type="video/mp4", expires_in=900)

    assert res.upload_url == "https://s3.ap-south-1.amazonaws.com/test-bucket/asset.mp4?sig=test"
    assert res.s3_key == s3_key
    mock_client.generate_presigned_url.assert_called_once_with(
        ClientMethod="put_object",
        Params={"Bucket": "test-bucket", "Key": s3_key, "ContentType": "video/mp4"},
        ExpiresIn=900,
        HttpMethod="PUT",
    )


def test_s3_storage_service_verify_object_mocked_client() -> None:
    mock_client = MagicMock()
    mock_client.head_object.return_value = {
        "ContentLength": 5242880,
        "ContentType": "video/mp4",
    }

    settings = Settings(AWS_S3_BUCKET="test-bucket", AWS_REGION="ap-south-1")
    service = S3StorageService(settings, client=mock_client)

    s3_key = "users/u1/projects/p1/media/m1/token.mp4"
    meta = service.verify_object(s3_key)

    assert meta.exists is True
    assert meta.size_bytes == 5242880
    assert meta.content_type == "video/mp4"

    # Test 404 ClientError handling
    mock_client.head_object.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
    )
    meta_missing = service.verify_object("missing-key")
    assert meta_missing.exists is False
    assert meta_missing.size_bytes == 0


def test_s3_storage_service_download_and_delete_mocked_client() -> None:
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = (
        "https://s3.ap-south-1.amazonaws.com/test-bucket/asset.mp4?token=xyz"
    )

    settings = Settings(AWS_S3_BUCKET="test-bucket", AWS_REGION="ap-south-1")
    service = S3StorageService(settings, client=mock_client)

    s3_key = "users/u1/projects/p1/media/m1/token.mp4"
    url = service.create_presigned_download_url(s3_key, expires_in=300, filename="my_cut.mp4")

    assert "token=xyz" in url
    mock_client.generate_presigned_url.assert_called_once_with(
        ClientMethod="get_object",
        Params={
            "Bucket": "test-bucket",
            "Key": s3_key,
            "ResponseContentDisposition": 'inline; filename="my_cut.mp4"',
        },
        ExpiresIn=300,
    )

    # Delete
    del_res = service.delete_object(s3_key)
    assert del_res is True
    mock_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key=s3_key)


def test_get_storage_service_factory_selection() -> None:
    # 1. Default (no bucket configured) -> returns MockStorageService
    default_settings = Settings(AWS_S3_BUCKET="")
    storage1 = get_storage_service(default_settings)
    assert isinstance(storage1, MockStorageService)

    # 2. Force mock via USE_MOCK_STORAGE -> returns MockStorageService even if bucket is set
    mock_forced_settings = Settings(AWS_S3_BUCKET="some-bucket", USE_MOCK_STORAGE=True)
    storage2 = get_storage_service(mock_forced_settings)
    assert isinstance(storage2, MockStorageService)
