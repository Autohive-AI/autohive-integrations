"""File inspection and rendering request contracts."""

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from figma.figma import figma

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("wrapped", [False, True])
async def test_image_fills_accepts_both_documented_shapes(mock_context, wrapped):
    images = {"image-reference": "https://example.com/fill.png"}
    payload = {"meta": {"images": images}, "status": 200, "error": False} if wrapped else {"images": images}
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=payload)
    result = await figma.execute_action("get_image_fills", {"file_key": "AbC123"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["images"] == images
    if wrapped:
        assert result.result.data["meta"] == payload["meta"]
    assert mock_context.fetch.call_args.args == ("https://api.figma.com/v1/files/AbC123/images",)


@pytest.mark.parametrize("payload", [{}, {"meta": {}}, {"images": []}, {"images": {"ref": 42}}])
async def test_image_fills_rejects_missing_or_malformed_maps(mock_context, payload):
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=payload)
    result = await figma.execute_action("get_image_fills", {"file_key": "AbC123"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "invalid image-fill map" in result.result.message


async def test_image_fills_keeps_api_errors(mock_context):
    mock_context.fetch.return_value = FetchResponse(status=403, headers={}, data={})
    result = await figma.execute_action("get_image_fills", {"file_key": "AbC123"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "403" in result.result.message


async def test_file_options_and_document_preserved(mock_context):
    data = {"name": "Design system", "document": {"id": "0:0", "type": "DOCUMENT"}, "branches": []}
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=data)
    result = await figma.execute_action(
        "get_file",
        {
            "file_key": "AbC123",
            "ids": ["1:2", "3:4"],
            "depth": 2,
            "geometry": "paths",
            "plugin_data": "shared",
            "version": "987",
            "branch_data": False,
        },
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data == data
    mock_context.fetch.assert_awaited_once_with(
        "https://api.figma.com/v1/files/AbC123",
        method="GET",
        headers={"Accept": "application/json"},
        params={
            "ids": "1:2,3:4",
            "depth": 2,
            "geometry": "paths",
            "plugin_data": "shared",
            "version": "987",
            "branch_data": "false",
        },
    )


async def test_missing_nodes_remain_null(mock_context):
    data = {"nodes": {"1:2": None, "3:4": {"document": {"id": "3:4", "type": "FRAME"}}}}
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=data)
    result = await figma.execute_action("get_file_nodes", {"file_key": "AbC123", "ids": ["1:2", "3:4"]}, mock_context)
    assert result.result.data == data
    assert mock_context.fetch.call_args.kwargs["params"] == {"ids": "1:2,3:4"}


async def test_export_query_and_partial_render(mock_context):
    mock_context.fetch.return_value = FetchResponse(
        status=200,
        headers={},
        data={
            "err": None,
            "images": {"1:2": "https://example.com/render.png", "3:4": None},
        },
    )
    result = await figma.execute_action(
        "export_images",
        {
            "file_key": "AbC123",
            "ids": ["1:2", "3:4"],
            "format": "svg",
            "scale": 4,
            "svg_outline_text": False,
            "use_absolute_bounds": True,
        },
        mock_context,
    )
    assert result.result.data["images"]["3:4"] is None
    assert mock_context.fetch.call_args.args == ("https://api.figma.com/v1/images/AbC123",)
    assert mock_context.fetch.call_args.kwargs["params"] == {
        "ids": "1:2,3:4",
        "format": "svg",
        "scale": 4,
        "svg_outline_text": "false",
        "use_absolute_bounds": "true",
    }


@pytest.mark.parametrize(
    "action,inputs",
    [
        ("get_file", {"file_key": "https://www.figma.com/design/AbC123/Test"}),
        ("get_file", {"file_key": "AbC123", "depth": 0}),
        ("get_file_nodes", {"file_key": "AbC123", "ids": []}),
        ("get_file_nodes", {"file_key": "AbC123", "ids": ["1:2,3:4"]}),
        ("export_images", {"file_key": "AbC123", "ids": ["1:2"], "scale": 4.1}),
        ("export_images", {"file_key": "AbC123", "ids": ["1:2"], "format": "gif"}),
    ],
)
async def test_invalid_file_inputs_do_not_call_api(mock_context, action, inputs):
    result = await figma.execute_action(action, inputs, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR
    mock_context.fetch.assert_not_awaited()
