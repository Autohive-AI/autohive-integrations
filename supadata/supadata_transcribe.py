from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler
)
from typing import Dict, Any
from supadata import Supadata, SupadataError

supadata_transcribe = Integration.load()

# ---- Action Handlers ----

@supadata_transcribe.action("get_transcript")
class GetTranscriptAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        video_url = inputs["video_url"]
        api_key = context.auth.get("credentials", {}).get("api_key", {})        
        try:
            supadata = Supadata(api_key=api_key)
            
            # Get transcript using the Supadata SDK
            transcript_response = supadata.transcript(
                url=video_url,
                text=False,  # Return timestamped chunks
                mode="auto"
            )
            
            # Format as SRT-style text
            formatted_transcript = self._format_as_srt(transcript_response.content)
            
            return {
                "transcript": formatted_transcript,
                "language": getattr(transcript_response, 'lang', ''),
                "available_languages": getattr(transcript_response, 'available_langs', [])
            }
            
        except SupadataError as e:
            raise ValueError(f"Supadata API error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error getting transcript: {str(e)}")
    
    def _format_as_srt(self, chunks):
        """Format transcript chunks as SRT-style text."""
        if isinstance(chunks, str):
            return chunks
        
        if not isinstance(chunks, list):
            return "chunks is in an invalid format"
        
        if not chunks:
            return ""
        
        formatted_lines = []
        for i, chunk in enumerate(chunks, 1):
            if hasattr(chunk, 'text') and hasattr(chunk, 'offset') and hasattr(chunk, 'duration'):
                start_time = self._ms_to_timestamp(chunk.offset)
                end_time = self._ms_to_timestamp(chunk.offset + chunk.duration)
                formatted_lines.append(f"{start_time} --> {end_time}")
                formatted_lines.append(chunk.text.strip())
                formatted_lines.append("")
        
        return "\n".join(formatted_lines)
    
    def _ms_to_timestamp(self, milliseconds):
        """Convert milliseconds to SRT timestamp format (HH:MM:SS,mmm)."""
        ms_int = int(milliseconds)
        hours = ms_int // 3600000
        minutes = (ms_int % 3600000) // 60000
        seconds = (ms_int % 60000) // 1000
        ms = ms_int % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"
    
