"""YouTube API upload handler for children's songs with COPPA compliance."""

import http.client
import httplib2
import logging
import os
import random
import time
from pathlib import Path
from typing import Dict, List, Optional

from .config import get_config
from .lyrics_generator import SongLyrics

logger = logging.getLogger(__name__)

# Maximum number of retries for resumable upload
MAX_RETRIES = 10
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]



class YouTubeUploader:
    """Handles video upload to YouTube with proper metadata and COPPA compliance."""

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    API_SERVICE_NAME = "youtube"
    API_VERSION = "v3"

    def __init__(self):
        """Initialize the YouTube uploader."""
        self.config = get_config()
        self.youtube_config = self.config.youtube
        self.service = None

    def authenticate(self) -> bool:
        """Authenticate with YouTube API using available credentials.

        Tries in order:
        1. Refresh token from environment
        2. Existing token.json file
        3. OAuth flow with client secrets

        Returns:
            True if authentication successful, False otherwise.
        """
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request

        creds = None

        # Method 1: Use refresh token from environment
        refresh_token = self.config.youtube_refresh_token
        client_id = self.config.youtube_client_id
        client_secret = self.config.youtube_client_secret

        if refresh_token and client_id and client_secret:
            logger.info("Authenticating with refresh token from environment")
            try:
                creds = Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=self.SCOPES,
                )
                creds.refresh(Request())
                logger.info("Successfully authenticated with refresh token")
            except Exception as e:
                logger.warning(f"Refresh token auth failed: {e}")
                creds = None

        # Method 2: Try existing token.json
        if creds is None:
            token_path = self.config.project_root / "token.json"
            if token_path.exists():
                logger.info("Authenticating with existing token.json")
                try:
                    creds = Credentials.from_authorized_user_file(
                        str(token_path), self.SCOPES
                    )
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    logger.info("Successfully authenticated with token.json")
                except Exception as e:
                    logger.warning(f"Token file auth failed: {e}")
                    creds = None

        # Method 3: OAuth flow
        if creds is None:
            client_secret_path = self.config.project_root / "client_secret.json"
            if client_secret_path.exists():
                logger.info("Starting OAuth flow with client_secret.json")
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(client_secret_path), self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                    # Save for future use
                    token_path = self.config.project_root / "token.json"
                    with open(token_path, "w") as token_file:
                        token_file.write(creds.to_json())
                    logger.info("OAuth flow completed and token saved")
                except Exception as e:
                    logger.error(f"OAuth flow failed: {e}")
                    return False
            else:
                logger.error(
                    "No authentication method available. "
                    "Set YOUTUBE_REFRESH_TOKEN env vars or provide client_secret.json"
                )
                return False

        if creds is None:
            return False

        # Build service
        self.service = self._build_service(creds)
        return self.service is not None


    def upload_video(
        self,
        video_path: str,
        song: SongLyrics,
        thumbnail_path: Optional[str] = None,
    ) -> Optional[str]:
        """Upload a video to YouTube with metadata.

        IMPORTANT: Sets selfDeclaredMadeForKids=True for COPPA compliance.

        Args:
            video_path: Path to the video file.
            song: SongLyrics instance for metadata.
            thumbnail_path: Optional path to thumbnail image.

        Returns:
            YouTube video ID if successful, None otherwise.
        """
        if self.service is None:
            if not self.authenticate():
                logger.error("Authentication failed, cannot upload")
                return None

        logger.info(f"Uploading video: {song.title}")

        # Build title from templates
        title_templates = self.youtube_config.get("title_templates", ["{song_name}"])
        title_template = random.choice(title_templates)
        title = title_template.format(
            song_name=song.title,
            topic=song.educational_topic.title(),
        )
        # YouTube title limit is 100 chars
        title = title[:100]

        # Build description
        description = self._build_description(song)

        # Build tags
        base_tags = self.youtube_config.get("base_tags", [])
        song_tags = song.suggested_tags or []
        category_tag = song.category.replace("_", " ")
        all_tags = list(set(base_tags + song_tags + [category_tag, song.educational_topic]))
        # YouTube allows max 500 chars total for tags
        tags = all_tags[:30]

        # Video metadata
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": self.youtube_config.get("category_id", "10"),
            },
            "status": {
                "privacyStatus": self.youtube_config.get("privacy_status", "public"),
                "selfDeclaredMadeForKids": True,  # COPPA compliance
            },
        }

        # Upload with resumable upload
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024,  # 1MB chunks
        )

        request = self.service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        video_id = self._resumable_upload(request)

        if video_id and thumbnail_path and os.path.exists(thumbnail_path):
            self._set_thumbnail(video_id, thumbnail_path)

        return video_id

    def _build_description(self, song: SongLyrics) -> str:
        """Build the YouTube video description from template.

        Args:
            song: SongLyrics instance.

        Returns:
            Formatted description string.
        """
        template = self.youtube_config.get("description_template", "{title}\n{description}")

        description = template.format(
            title=song.title,
            description=song.description,
            topic=song.educational_topic,
            lyrics=song.lyrics,
        )

        # YouTube description limit is 5000 chars
        return description[:5000]


    def _resumable_upload(self, request) -> Optional[str]:
        """Execute a resumable upload with retry logic.

        Args:
            request: YouTube API insert request.

        Returns:
            Video ID if successful, None otherwise.
        """
        response = None
        error = None
        retry = 0

        while response is None:
            try:
                logger.info("Uploading chunk...")
                status, response = request.next_chunk()
                if status:
                    logger.info(f"Upload progress: {int(status.progress() * 100)}%")
                if response:
                    video_id = response.get("id")
                    logger.info(f"Upload complete! Video ID: {video_id}")
                    return video_id
            except http.client.HTTPException as e:
                error = f"HTTP error: {e}"
                retry += 1
            except Exception as e:
                error_str = str(e)
                if "retriable" in error_str.lower() or retry < MAX_RETRIES:
                    error = f"Retriable error: {e}"
                    retry += 1
                else:
                    logger.error(f"Upload failed with non-retriable error: {e}")
                    return None

            if retry > MAX_RETRIES:
                logger.error(f"Upload failed after {MAX_RETRIES} retries. Last error: {error}")
                return None

            # Exponential backoff
            sleep_seconds = random.random() * (2 ** retry)
            logger.warning(f"Retry {retry}/{MAX_RETRIES} after {sleep_seconds:.1f}s. Error: {error}")
            time.sleep(sleep_seconds)

        return None

    def _set_thumbnail(self, video_id: str, thumbnail_path: str) -> bool:
        """Set the thumbnail for an uploaded video.

        Args:
            video_id: YouTube video ID.
            thumbnail_path: Path to thumbnail image.

        Returns:
            True if successful, False otherwise.
        """
        try:
            from googleapiclient.http import MediaFileUpload

            media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
            self.service.thumbnails().set(
                videoId=video_id,
                media_body=media,
            ).execute()
            logger.info(f"Thumbnail set for video {video_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to set thumbnail: {e}")
            return False

    def _build_service(self, credentials):
        """Build the YouTube API service object.

        Args:
            credentials: Google OAuth2 credentials.

        Returns:
            YouTube API service object or None.
        """
        try:
            from googleapiclient.discovery import build

            service = build(
                self.API_SERVICE_NAME,
                self.API_VERSION,
                credentials=credentials,
            )
            return service
        except Exception as e:
            logger.error(f"Failed to build YouTube service: {e}")
            return None



class YouTubeSetup:
    """Helper class for initial YouTube API setup and token generation."""

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

    def __init__(self, client_secret_path: str = None):
        """Initialize YouTube setup helper.

        Args:
            client_secret_path: Path to client_secret.json from Google Cloud Console.
        """
        config = get_config()
        if client_secret_path is None:
            client_secret_path = str(config.project_root / "client_secret.json")
        self.client_secret_path = client_secret_path

    def generate_refresh_token(self) -> Optional[str]:
        """Run OAuth flow to generate a refresh token.

        Returns:
            Refresh token string if successful, None otherwise.
        """
        from google_auth_oauthlib.flow import InstalledAppFlow

        if not os.path.exists(self.client_secret_path):
            logger.error(f"Client secret file not found: {self.client_secret_path}")
            self.print_instructions()
            return None

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.client_secret_path, self.SCOPES
            )
            credentials = flow.run_local_server(port=8080)

            refresh_token = credentials.refresh_token
            if refresh_token:
                logger.info("Refresh token generated successfully!")
                print(f"\n{'='*60}")
                print("SUCCESS! Your refresh token:")
                print(f"{'='*60}")
                print(f"\nYOUTUBE_REFRESH_TOKEN={refresh_token}")
                print(f"\n{'='*60}")
                print("Add this to your .env file.")
                print(f"{'='*60}\n")

                # Also save token.json for direct use
                config = get_config()
                token_path = config.project_root / "token.json"
                with open(token_path, "w") as f:
                    f.write(credentials.to_json())
                logger.info(f"Token also saved to {token_path}")

                return refresh_token
            else:
                logger.error("No refresh token received. Try again with access_type=offline.")
                return None

        except Exception as e:
            logger.error(f"OAuth flow error: {e}")
            return None

    @staticmethod
    def print_instructions():
        """Print setup instructions for YouTube API credentials."""
        instructions = """
╔══════════════════════════════════════════════════════════════════╗
║              YouTube API Setup Instructions                       ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  1. Go to https://console.cloud.google.com/                      ║
║  2. Create a new project (or select existing)                    ║
║  3. Enable the "YouTube Data API v3"                             ║
║  4. Go to Credentials → Create Credentials → OAuth Client ID    ║
║  5. Application type: "Desktop app"                              ║
║  6. Download the JSON file                                       ║
║  7. Rename it to "client_secret.json"                            ║
║  8. Place it in the project root directory                       ║
║  9. Run: python main.py --setup-youtube                          ║
║                                                                  ║
║  After setup, add these to your .env file:                       ║
║    YOUTUBE_CLIENT_ID=<from client_secret.json>                   ║
║    YOUTUBE_CLIENT_SECRET=<from client_secret.json>               ║
║    YOUTUBE_REFRESH_TOKEN=<generated during setup>                ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""
        print(instructions)
