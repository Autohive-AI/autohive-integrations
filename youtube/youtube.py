

from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler
)
from typing import Dict, Any, List, Optional
import base64
from io import BytesIO
from PIL import Image

# Initialize the integration using the config.json file
youtube = Integration.load()

# Base endpoint for YouTube Data API v3
service_endpoint = "https://www.googleapis.com/youtube/v3/"


class YouTubeParser:
    """
    Utility class for parsing YouTube API responses.

    This class provides static methods to transform raw API responses into
    clean, structured dictionaries with consistent field naming and data extraction.
    """

    @staticmethod
    def parse_search_result(item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a search result item from YouTube API.

        Extracts relevant information from search results including video/channel/playlist
        details, thumbnails, and metadata.

        Args:
            item: Raw search result item from YouTube API

        Returns:
            Dictionary containing parsed search result with fields:
                - id: Resource ID (video/channel/playlist)
                - title: Resource title
                - description: Resource description
                - thumbnail: Best available thumbnail URL
                - published_at: Publication timestamp
                - channel_title: Channel name
                - channel_id: Channel ID
        """
        snippet = item.get('snippet', {})
        thumbnails = snippet.get('thumbnails', {})
        default_thumbnail = thumbnails.get('high', thumbnails.get('medium', thumbnails.get('default', {})))

        return {
            "id": item.get('id', {}),
            "title": snippet.get('title', ''),
            "description": snippet.get('description', ''),
            "thumbnail": default_thumbnail.get('url', ''),
            "published_at": snippet.get('publishedAt', ''),
            "channel_title": snippet.get('channelTitle', ''),
            "channel_id": snippet.get('channelId', '')
        }

    @staticmethod
    def parse_video(item: Dict[str, Any]) -> Dict[str, Any]:
        """Parse video details."""
        snippet = item.get('snippet', {})
        statistics = item.get('statistics', {})
        content_details = item.get('contentDetails', {})

        video = {
            "id": item.get('id', ''),
            "title": snippet.get('title', ''),
            "description": snippet.get('description', ''),
            "channel_id": snippet.get('channelId', ''),
            "channel_title": snippet.get('channelTitle', ''),
            "published_at": snippet.get('publishedAt', ''),
            "thumbnails": snippet.get('thumbnails', {}),
        }

        # Add content details
        if 'duration' in content_details:
            video['duration'] = content_details['duration']

        # Add statistics
        if 'viewCount' in statistics:
            video['view_count'] = statistics['viewCount']
        if 'likeCount' in statistics:
            video['like_count'] = statistics['likeCount']
        if 'commentCount' in statistics:
            video['comment_count'] = statistics['commentCount']

        # Add tags
        if 'tags' in snippet:
            video['tags'] = snippet['tags']

        return video

    @staticmethod
    def parse_channel(item: Dict[str, Any]) -> Dict[str, Any]:
        """Parse channel details."""
        snippet = item.get('snippet', {})
        statistics = item.get('statistics', {})

        channel = {
            "id": item.get('id', ''),
            "title": snippet.get('title', ''),
            "description": snippet.get('description', ''),
            "custom_url": snippet.get('customUrl', ''),
            "published_at": snippet.get('publishedAt', ''),
            "thumbnails": snippet.get('thumbnails', {})
        }

        # Add statistics
        if 'subscriberCount' in statistics:
            channel['subscriber_count'] = statistics['subscriberCount']
        if 'videoCount' in statistics:
            channel['video_count'] = statistics['videoCount']
        if 'viewCount' in statistics:
            channel['view_count'] = statistics['viewCount']

        return channel

    @staticmethod
    def parse_playlist(item: Dict[str, Any]) -> Dict[str, Any]:
        """Parse playlist details."""
        snippet = item.get('snippet', {})
        content_details = item.get('contentDetails', {})

        playlist = {
            "id": item.get('id', ''),
            "title": snippet.get('title', ''),
            "description": snippet.get('description', ''),
            "channel_id": snippet.get('channelId', ''),
            "channel_title": snippet.get('channelTitle', ''),
            "published_at": snippet.get('publishedAt', ''),
            "thumbnails": snippet.get('thumbnails', {})
        }

        if 'itemCount' in content_details:
            playlist['item_count'] = content_details['itemCount']

        return playlist

    @staticmethod
    def parse_comment(item: Dict[str, Any]) -> Dict[str, Any]:
        """Parse comment details."""
        snippet = item.get('snippet', {})
        top_level_comment = snippet.get('topLevelComment', {})
        comment_snippet = top_level_comment.get('snippet', snippet)

        return {
            "id": item.get('id', top_level_comment.get('id', '')),
            "text": comment_snippet.get('textDisplay', ''),
            "text_original": comment_snippet.get('textOriginal', ''),
            "author_display_name": comment_snippet.get('authorDisplayName', ''),
            "author_channel_id": comment_snippet.get('authorChannelId', {}).get('value', ''),
            "like_count": comment_snippet.get('likeCount', 0),
            "published_at": comment_snippet.get('publishedAt', ''),
            "updated_at": comment_snippet.get('updatedAt', ''),
            "total_reply_count": snippet.get('totalReplyCount', 0)
        }


# ---- Search ----

@youtube.action("search")
class Search(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                "part": "snippet",
                "q": inputs['query']
            }

            # Add optional parameters
            if 'type' in inputs:
                params['type'] = inputs['type']
            if 'max_results' in inputs:
                params['maxResults'] = inputs['max_results']
            else:
                params['maxResults'] = 5
            if 'order' in inputs:
                params['order'] = inputs['order']
            if 'published_after' in inputs:
                params['publishedAfter'] = inputs['published_after']
            if 'published_before' in inputs:
                params['publishedBefore'] = inputs['published_before']
            if 'channel_id' in inputs:
                params['channelId'] = inputs['channel_id']
            if 'region_code' in inputs:
                params['regionCode'] = inputs['region_code']
            if 'page_token' in inputs:
                params['pageToken'] = inputs['page_token']

            response = await context.fetch(
                service_endpoint + "search",
                method="GET",
                params=params
            )

            items = []
            for item in response.get('items', []):
                items.append(YouTubeParser.parse_search_result(item))

            result = {
                "items": items,
                "total_results": response.get('pageInfo', {}).get('totalResults', 0),
                "result": True
            }

            if 'nextPageToken' in response:
                result['next_page_token'] = response['nextPageToken']

            return result

        except Exception as e:
            return {
                "items": [],
                "total_results": 0,
                "result": False,
                "error": str(e)
            }


# ---- Video Management ----

@youtube.action("get_video")
class GetVideo(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            response = await context.fetch(
                service_endpoint + "videos",
                method="GET",
                params={
                    "part": "snippet,statistics,contentDetails",
                    "id": inputs['video_id']
                }
            )

            items = response.get('items', [])
            if not items:
                return {
                    "video": {},
                    "result": False,
                    "error": "Video not found"
                }

            video = YouTubeParser.parse_video(items[0])

            return {
                "video": video,
                "result": True
            }

        except Exception as e:
            return {
                "video": {},
                "result": False,
                "error": str(e)
            }


@youtube.action("update_video")
class UpdateVideo(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            video_id = inputs['video_id']

            # First, get the existing video
            existing_response = await context.fetch(
                service_endpoint + "videos",
                method="GET",
                params={
                    "part": "snippet,status",
                    "id": video_id
                }
            )

            items = existing_response.get('items', [])
            if not items:
                return {
                    "video": {},
                    "result": False,
                    "error": "Video not found"
                }

            existing_video = items[0]
            snippet = existing_video.get('snippet', {})
            status = existing_video.get('status', {})

            # Update fields that were provided
            if 'title' in inputs:
                snippet['title'] = inputs['title']
            if 'description' in inputs:
                snippet['description'] = inputs['description']
            if 'category_id' in inputs:
                snippet['categoryId'] = inputs['category_id']
            if 'tags' in inputs:
                snippet['tags'] = inputs['tags']
            if 'privacy_status' in inputs:
                status['privacyStatus'] = inputs['privacy_status']
            if 'made_for_kids' in inputs:
                status['selfDeclaredMadeForKids'] = inputs['made_for_kids']

            # Update the video
            update_data = {
                "id": video_id,
                "snippet": snippet,
                "status": status
            }

            response = await context.fetch(
                service_endpoint + "videos",
                method="PUT",
                params={"part": "snippet,status"},
                json=update_data
            )

            return {
                "video": YouTubeParser.parse_video(response),
                "result": True
            }

        except Exception as e:
            return {
                "video": {},
                "result": False,
                "error": str(e)
            }


@youtube.action("upload_thumbnail")
class UploadThumbnail(ActionHandler):
    def _compress_image(self, image_data: bytes, max_size_mb: float = 2.0) -> tuple[bytes, str]:
        """
        Compress image if it's larger than max_size_mb.
        Returns: (compressed_image_data, mimetype)
        """
        max_size_bytes = max_size_mb * 1024 * 1024

        # If image is already small enough, return as-is
        if len(image_data) <= max_size_bytes:
            # Determine mimetype
            mimetype = "image/jpeg"
            if image_data[:4] == b'\x89PNG':
                mimetype = "image/png"
            elif image_data[:2] == b'\xff\xd8':
                mimetype = "image/jpeg"
            return image_data, mimetype

        # Open the image
        img = Image.open(BytesIO(image_data))

        # Convert RGBA to RGB if necessary (for JPEG compatibility)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Start with quality 85 and reduce until size is acceptable
        quality = 85
        while quality > 20:
            output = BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            compressed_data = output.getvalue()

            if len(compressed_data) <= max_size_bytes:
                return compressed_data, "image/jpeg"

            quality -= 5

        # If still too large, resize the image
        output = BytesIO()
        current_size = img.size
        scale_factor = 0.9

        while len(compressed_data) > max_size_bytes and min(current_size) > 100:
            new_size = (int(current_size[0] * scale_factor), int(current_size[1] * scale_factor))
            resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
            output = BytesIO()
            resized_img.save(output, format='JPEG', quality=85, optimize=True)
            compressed_data = output.getvalue()
            current_size = new_size

        return compressed_data, "image/jpeg"

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            video_id = inputs['video_id']

            # Support multiple input methods: image_url, image_path, file, files
            image_url = inputs.get('image_url') or inputs.get('image_path')
            file_obj = inputs.get('file')
            files_arr = inputs.get('files')

            # Handle files array - use first file if multiple provided
            if not file_obj and isinstance(files_arr, list) and files_arr:
                file_obj = files_arr[0]

            # Get image data based on input type
            image_data = None

            if file_obj:
                # Handle chat-uploaded file object with base64 content
                content_b64 = file_obj.get('content')
                if content_b64:
                    image_data = base64.b64decode(content_b64)
                else:
                    return {
                        "thumbnail": {},
                        "result": False,
                        "error": "File object missing 'content' field"
                    }
            elif image_url:
                # Fetch the image data from the URL (including conversation file:// URLs)
                image_response = await context.fetch(
                    image_url,
                    method="GET"
                )

                # Get the image content as bytes
                if isinstance(image_response, bytes):
                    image_data = image_response
                elif isinstance(image_response, dict) and 'content' in image_response:
                    image_data = image_response['content']
                else:
                    image_data = str(image_response).encode()
            else:
                return {
                    "thumbnail": {},
                    "result": False,
                    "error": "Either image_url, image_path, file, or files must be provided"
                }

            # Compress image if larger than 2 MB
            original_size = len(image_data)
            image_data, mimetype = self._compress_image(image_data, max_size_mb=2.0)
            compressed_size = len(image_data)

            # Log compression if it occurred
            compression_info = {}
            if original_size > compressed_size:
                compression_info = {
                    "original_size_mb": round(original_size / (1024 * 1024), 2),
                    "compressed_size_mb": round(compressed_size / (1024 * 1024), 2),
                    "reduction_percent": round(((original_size - compressed_size) / original_size) * 100, 2)
                }

            # Upload the thumbnail directly using raw bytes
            # YouTube API expects raw image data in the request body with appropriate Content-Type
            response = await context.fetch(
                url=f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set",
                method="POST",
                params={"videoId": video_id},
                data=image_data,
                headers={"Content-Type": mimetype}
            )

            result = {
                "thumbnail": response,
                "result": True
            }

            # Add compression info if compression occurred
            if compression_info:
                result["compression_info"] = compression_info

            return result

        except Exception as e:
            return {
                "thumbnail": {},
                "result": False,
                "error": str(e)
            }


# ---- Channel Management ----

@youtube.action("get_channel")
class GetChannel(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                "part": "snippet,statistics,contentDetails"
            }

            # Determine which filter to use
            if inputs.get('mine'):
                params['mine'] = 'true'
            elif 'channel_id' in inputs:
                params['id'] = inputs['channel_id']
            elif 'channel_handle' in inputs:
                params['forHandle'] = inputs['channel_handle']
            else:
                return {
                    "channel": {},
                    "result": False,
                    "error": "Must provide channel_id, channel_handle, or set mine=true"
                }

            response = await context.fetch(
                service_endpoint + "channels",
                method="GET",
                params=params
            )

            items = response.get('items', [])
            if not items:
                return {
                    "channel": {},
                    "result": False,
                    "error": "Channel not found"
                }

            channel = YouTubeParser.parse_channel(items[0])

            return {
                "channel": channel,
                "result": True
            }

        except Exception as e:
            return {
                "channel": {},
                "result": False,
                "error": str(e)
            }


# ---- Playlist Management ----

@youtube.action("list_playlists")
class ListPlaylists(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                "part": "snippet,contentDetails",
                "maxResults": inputs.get('max_results', 5)
            }

            if inputs.get('mine'):
                params['mine'] = 'true'
            elif 'channel_id' in inputs:
                params['channelId'] = inputs['channel_id']
            else:
                return {
                    "playlists": [],
                    "result": False,
                    "error": "Must provide channel_id or set mine=true"
                }

            if 'page_token' in inputs:
                params['pageToken'] = inputs['page_token']

            response = await context.fetch(
                service_endpoint + "playlists",
                method="GET",
                params=params
            )

            playlists = []
            for item in response.get('items', []):
                playlists.append(YouTubeParser.parse_playlist(item))

            result = {
                "playlists": playlists,
                "result": True
            }

            if 'nextPageToken' in response:
                result['next_page_token'] = response['nextPageToken']

            return result

        except Exception as e:
            return {
                "playlists": [],
                "result": False,
                "error": str(e)
            }


@youtube.action("create_playlist")
class CreatePlaylist(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            playlist_data = {
                "snippet": {
                    "title": inputs['title']
                },
                "status": {
                    "privacyStatus": inputs['privacy_status']
                }
            }

            if 'description' in inputs:
                playlist_data['snippet']['description'] = inputs['description']

            response = await context.fetch(
                service_endpoint + "playlists",
                method="POST",
                params={"part": "snippet,status"},
                json=playlist_data
            )

            return {
                "playlist": YouTubeParser.parse_playlist(response),
                "result": True
            }

        except Exception as e:
            return {
                "playlist": {},
                "result": False,
                "error": str(e)
            }


@youtube.action("update_playlist")
class UpdatePlaylist(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            playlist_id = inputs['playlist_id']

            # Get existing playlist
            existing_response = await context.fetch(
                service_endpoint + "playlists",
                method="GET",
                params={
                    "part": "snippet,status",
                    "id": playlist_id
                }
            )

            items = existing_response.get('items', [])
            if not items:
                return {
                    "playlist": {},
                    "result": False,
                    "error": "Playlist not found"
                }

            existing_playlist = items[0]
            snippet = existing_playlist.get('snippet', {})
            status = existing_playlist.get('status', {})

            # Update fields
            if 'title' in inputs:
                snippet['title'] = inputs['title']
            if 'description' in inputs:
                snippet['description'] = inputs['description']
            if 'privacy_status' in inputs:
                status['privacyStatus'] = inputs['privacy_status']

            update_data = {
                "id": playlist_id,
                "snippet": snippet,
                "status": status
            }

            response = await context.fetch(
                service_endpoint + "playlists",
                method="PUT",
                params={"part": "snippet,status"},
                json=update_data
            )

            return {
                "playlist": YouTubeParser.parse_playlist(response),
                "result": True
            }

        except Exception as e:
            return {
                "playlist": {},
                "result": False,
                "error": str(e)
            }


@youtube.action("delete_playlist")
class DeletePlaylist(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            await context.fetch(
                service_endpoint + "playlists",
                method="DELETE",
                params={"id": inputs['playlist_id']}
            )

            return {"result": True}

        except Exception as e:
            return {
                "result": False,
                "error": str(e)
            }


@youtube.action("list_playlist_items")
class ListPlaylistItems(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                "part": "snippet,contentDetails",
                "playlistId": inputs['playlist_id'],
                "maxResults": inputs.get('max_results', 5)
            }

            if 'page_token' in inputs:
                params['pageToken'] = inputs['page_token']

            response = await context.fetch(
                service_endpoint + "playlistItems",
                method="GET",
                params=params
            )

            items = []
            for item in response.get('items', []):
                snippet = item.get('snippet', {})
                content_details = item.get('contentDetails', {})
                items.append({
                    "id": item.get('id', ''),
                    "video_id": content_details.get('videoId', ''),
                    "title": snippet.get('title', ''),
                    "description": snippet.get('description', ''),
                    "position": snippet.get('position', 0),
                    "published_at": snippet.get('publishedAt', ''),
                    "thumbnails": snippet.get('thumbnails', {})
                })

            result = {
                "items": items,
                "result": True
            }

            if 'nextPageToken' in response:
                result['next_page_token'] = response['nextPageToken']

            return result

        except Exception as e:
            return {
                "items": [],
                "result": False,
                "error": str(e)
            }


@youtube.action("add_video_to_playlist")
class AddVideoToPlaylist(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            playlist_item_data = {
                "snippet": {
                    "playlistId": inputs['playlist_id'],
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": inputs['video_id']
                    }
                }
            }

            if 'position' in inputs:
                playlist_item_data['snippet']['position'] = inputs['position']

            response = await context.fetch(
                service_endpoint + "playlistItems",
                method="POST",
                params={"part": "snippet"},
                json=playlist_item_data
            )

            return {
                "playlist_item": response,
                "result": True
            }

        except Exception as e:
            return {
                "playlist_item": {},
                "result": False,
                "error": str(e)
            }


@youtube.action("remove_video_from_playlist")
class RemoveVideoFromPlaylist(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            await context.fetch(
                service_endpoint + "playlistItems",
                method="DELETE",
                params={"id": inputs['playlist_item_id']}
            )

            return {"result": True}

        except Exception as e:
            return {
                "result": False,
                "error": str(e)
            }


# ---- Comment Management ----

@youtube.action("list_comments")
class ListComments(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                "part": "snippet",
                "videoId": inputs['video_id'],
                "maxResults": inputs.get('max_results', 20),
                "textFormat": "plainText"
            }

            if 'order' in inputs:
                params['order'] = inputs['order']
            if 'page_token' in inputs:
                params['pageToken'] = inputs['page_token']

            response = await context.fetch(
                service_endpoint + "commentThreads",
                method="GET",
                params=params
            )

            comments = []
            for item in response.get('items', []):
                comments.append(YouTubeParser.parse_comment(item))

            result = {
                "comments": comments,
                "result": True
            }

            if 'nextPageToken' in response:
                result['next_page_token'] = response['nextPageToken']

            return result

        except Exception as e:
            return {
                "comments": [],
                "result": False,
                "error": str(e)
            }


@youtube.action("list_comment_replies")
class ListCommentReplies(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                "part": "snippet",
                "parentId": inputs['parent_comment_id'],
                "maxResults": inputs.get('max_results', 20),
                "textFormat": "plainText"
            }

            if 'page_token' in inputs:
                params['pageToken'] = inputs['page_token']

            response = await context.fetch(
                service_endpoint + "comments",
                method="GET",
                params=params
            )

            replies = []
            for item in response.get('items', []):
                snippet = item.get('snippet', {})
                replies.append({
                    "id": item.get('id', ''),
                    "text": snippet.get('textDisplay', ''),
                    "author_display_name": snippet.get('authorDisplayName', ''),
                    "like_count": snippet.get('likeCount', 0),
                    "published_at": snippet.get('publishedAt', '')
                })

            result = {
                "replies": replies,
                "result": True
            }

            if 'nextPageToken' in response:
                result['next_page_token'] = response['nextPageToken']

            return result

        except Exception as e:
            return {
                "replies": [],
                "result": False,
                "error": str(e)
            }


@youtube.action("post_comment")
class PostComment(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            comment_data = {
                "snippet": {
                    "videoId": inputs['video_id'],
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": inputs['text']
                        }
                    }
                }
            }

            response = await context.fetch(
                service_endpoint + "commentThreads",
                method="POST",
                params={"part": "snippet"},
                json=comment_data
            )

            return {
                "comment": YouTubeParser.parse_comment(response),
                "result": True
            }

        except Exception as e:
            return {
                "comment": {},
                "result": False,
                "error": str(e)
            }


@youtube.action("reply_to_comment")
class ReplyToComment(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            reply_data = {
                "snippet": {
                    "parentId": inputs['parent_comment_id'],
                    "textOriginal": inputs['text']
                }
            }

            response = await context.fetch(
                service_endpoint + "comments",
                method="POST",
                params={"part": "snippet"},
                json=reply_data
            )

            snippet = response.get('snippet', {})
            return {
                "comment": {
                    "id": response.get('id', ''),
                    "text": snippet.get('textDisplay', ''),
                    "author_display_name": snippet.get('authorDisplayName', '')
                },
                "result": True
            }

        except Exception as e:
            return {
                "comment": {},
                "result": False,
                "error": str(e)
            }


@youtube.action("update_comment")
class UpdateComment(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            comment_id = inputs['comment_id']

            # Get existing comment
            existing_response = await context.fetch(
                service_endpoint + "comments",
                method="GET",
                params={
                    "part": "snippet",
                    "id": comment_id
                }
            )

            items = existing_response.get('items', [])
            if not items:
                return {
                    "comment": {},
                    "result": False,
                    "error": "Comment not found"
                }

            existing_comment = items[0]
            snippet = existing_comment.get('snippet', {})
            snippet['textOriginal'] = inputs['text']

            update_data = {
                "id": comment_id,
                "snippet": snippet
            }

            response = await context.fetch(
                service_endpoint + "comments",
                method="PUT",
                params={"part": "snippet"},
                json=update_data
            )

            return {
                "comment": response,
                "result": True
            }

        except Exception as e:
            return {
                "comment": {},
                "result": False,
                "error": str(e)
            }


@youtube.action("delete_comment")
class DeleteComment(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            await context.fetch(
                service_endpoint + "comments",
                method="DELETE",
                params={"id": inputs['comment_id']}
            )

            return {"result": True}

        except Exception as e:
            return {
                "result": False,
                "error": str(e)
            }


@youtube.action("moderate_comment")
class ModerateComment(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            params = {
                "id": inputs['comment_id'],
                "moderationStatus": inputs['moderation_status']
            }

            if inputs.get('ban_author', False):
                params['banAuthor'] = 'true'

            await context.fetch(
                service_endpoint + "comments/setModerationStatus",
                method="POST",
                params=params
            )

            return {"result": True}

        except Exception as e:
            return {
                "result": False,
                "error": str(e)
            }
