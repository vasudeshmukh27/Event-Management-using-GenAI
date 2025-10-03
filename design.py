"""
AI-Powered Design Generation for Event Management
Handles poster creation using Stable Diffusion XL and text overlay
"""

import os
import io
import base64
import logging
from typing import Optional, Dict, List, Tuple
from PIL import Image, ImageDraw, ImageFont
import requests
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PosterGenerator:
    """
    AI-powered poster generation using Stable Diffusion XL and PIL
    Supports both local SDXL generation and text overlay composition
    """
    
    def __init__(self, use_local_sdxl: bool = False):
        """
        Initialize the poster generator
        
        Args:
            use_local_sdxl: If True, load SDXL locally (requires GPU/CPU). If False, use placeholders.
        """
        self.use_local_sdxl = use_local_sdxl
        self.pipeline = None
        
        # Default design templates
        self.templates = {
            "tech_conference": {
                "background_prompt": "Modern technology conference background, blue gradients, geometric shapes, professional, clean design, high quality",
                "colors": {"primary": "#2E86AB", "secondary": "#A23B72", "text": "#FFFFFF"},
                "font_size_title": 72,
                "font_size_subtitle": 36,
                "font_size_details": 24
            },
            "academic": {
                "background_prompt": "Academic conference poster background, elegant blue and white, scholarly design, professional presentation",
                "colors": {"primary": "#1E3A8A", "secondary": "#3B82F6", "text": "#1F2937"},
                "font_size_title": 64,
                "font_size_subtitle": 32,
                "font_size_details": 20
            },
            "creative": {
                "background_prompt": "Creative workshop poster, vibrant colors, artistic elements, inspirational design, modern aesthetic",
                "colors": {"primary": "#7C3AED", "secondary": "#F59E0B", "text": "#FFFFFF"},
                "font_size_title": 80,
                "font_size_subtitle": 40,
                "font_size_details": 28
            },
            "business": {
                "background_prompt": "Business summit poster, corporate colors, professional gradient, clean modern design",
                "colors": {"primary": "#059669", "secondary": "#10B981", "text": "#FFFFFF"},
                "font_size_title": 68,
                "font_size_subtitle": 34,
                "font_size_details": 22
            }
        }
        
        if use_local_sdxl:
            self._load_sdxl_pipeline()
    
    def _load_sdxl_pipeline(self):
        """
        Load SDXL pipeline for local generation
        Note: This requires significant compute resources
        """
        try:
            from diffusers import StableDiffusionXLPipeline
            import torch
            
            logger.info("Loading SDXL pipeline (this may take a few minutes)...")
            
            # Load SDXL base model
            self.pipeline = StableDiffusionXLPipeline.from_pretrained(
                "stabilityai/stable-diffusion-xl-base-1.0",
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                use_safetensors=True
            )
            
            if torch.cuda.is_available():
                self.pipeline = self.pipeline.to("cuda")
                logger.info("SDXL loaded on GPU")
            else:
                logger.info("SDXL loaded on CPU (will be slower)")
                
        except Exception as e:
            logger.error(f"Failed to load SDXL: {e}")
            logger.info("Falling back to placeholder generation")
            self.use_local_sdxl = False
            self.pipeline = None
    
    def generate_background(self, template: str = "tech_conference", 
                          custom_prompt: Optional[str] = None,
                          width: int = 1024, height: int = 1024) -> Image.Image:
        """
        Generate background image using SDXL or create placeholder
        
        Args:
            template: Template name from available templates
            custom_prompt: Custom prompt override
            width: Image width
            height: Image height
            
        Returns:
            PIL Image background
        """
        if self.use_local_sdxl and self.pipeline:
            return self._generate_sdxl_background(template, custom_prompt, width, height)
        else:
            return self._generate_placeholder_background(template, width, height)
    
    def _generate_sdxl_background(self, template: str, custom_prompt: Optional[str],
                                width: int, height: int) -> Image.Image:
        """
        Generate background using SDXL pipeline
        """
        try:
            prompt = custom_prompt or self.templates[template]["background_prompt"]
            
            logger.info(f"Generating SDXL background with prompt: {prompt}")
            
            # Generate image
            result = self.pipeline(
                prompt=prompt,
                width=width,
                height=height,
                num_inference_steps=20,
                guidance_scale=7.5
            )
            
            return result.images[0]
            
        except Exception as e:
            logger.error(f"SDXL generation failed: {e}")
            return self._generate_placeholder_background(template, width, height)
    
    def _generate_placeholder_background(self, template: str, width: int, height: int) -> Image.Image:
        """
        Generate gradient placeholder background
        """
        logger.info(f"Generating placeholder background for template: {template}")
        
        # Create gradient background
        img = Image.new('RGB', (width, height))
        colors = self.templates.get(template, self.templates["tech_conference"])["colors"]
        
        # Simple gradient from primary to secondary color
        primary = self._hex_to_rgb(colors["primary"])
        secondary = self._hex_to_rgb(colors["secondary"])
        
        for y in range(height):
            # Calculate blend ratio
            ratio = y / height
            r = int(primary[0] * (1 - ratio) + secondary[0] * ratio)
            g = int(primary[1] * (1 - ratio) + secondary[1] * ratio)
            b = int(primary[2] * (1 - ratio) + secondary[2] * ratio)
            
            # Draw horizontal line
            draw = ImageDraw.Draw(img)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        return img
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def add_text_overlay(self, background: Image.Image, event_data: Dict,
                        template: str = "tech_conference") -> Image.Image:
        """
        Add text overlay to background image
        
        Args:
            background: Background PIL Image
            event_data: Dictionary with event information
            template: Design template to use
            
        Returns:
            PIL Image with text overlay
        """
        logger.info("Adding text overlay to poster")
        
        # Create a copy to avoid modifying original
        img = background.copy()
        draw = ImageDraw.Draw(img)
        
        # Get template settings
        template_config = self.templates.get(template, self.templates["tech_conference"])
        text_color = template_config["colors"]["text"]
        
        # Try to load custom fonts, fallback to default
        try:
            title_font = ImageFont.truetype("arial.ttf", template_config["font_size_title"])
            subtitle_font = ImageFont.truetype("arial.ttf", template_config["font_size_subtitle"])
            detail_font = ImageFont.truetype("arial.ttf", template_config["font_size_details"])
        except:
            # Fallback to default fonts
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            detail_font = ImageFont.load_default()
        
        # Calculate positions (centered layout)
        img_width, img_height = img.size
        
        # Title
        title = event_data.get('title', 'Event Title')
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (img_width - title_width) // 2
        title_y = img_height // 4
        
        draw.text((title_x, title_y), title, font=title_font, fill=text_color)
        
        # Subtitle/Date
        subtitle = event_data.get('date', 'Event Date')
        subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
        subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
        subtitle_x = (img_width - subtitle_width) // 2
        subtitle_y = title_y + template_config["font_size_title"] + 20
        
        draw.text((subtitle_x, subtitle_y), subtitle, font=subtitle_font, fill=text_color)
        
        # Venue
        venue = event_data.get('venue', 'Event Venue')
        venue_bbox = draw.textbbox((0, 0), venue, font=detail_font)
        venue_width = venue_bbox[2] - venue_bbox[0]
        venue_x = (img_width - venue_width) // 2
        venue_y = subtitle_y + template_config["font_size_subtitle"] + 40
        
        draw.text((venue_x, venue_y), venue, font=detail_font, fill=text_color)
        
        # Additional details
        if 'details' in event_data:
            details = event_data['details']
            details_bbox = draw.textbbox((0, 0), details, font=detail_font)
            details_width = details_bbox[2] - details_bbox[0]
            details_x = (img_width - details_width) // 2
            details_y = venue_y + template_config["font_size_details"] + 30
            
            draw.text((details_x, details_y), details, font=detail_font, fill=text_color)
        
        return img
    
    def create_poster(self, event_data: Dict, template: str = "tech_conference",
                     custom_prompt: Optional[str] = None,
                     width: int = 1024, height: int = 1024) -> Image.Image:
        """
        Create complete poster with background and text overlay
        
        Args:
            event_data: Event information dictionary
            template: Design template to use
            custom_prompt: Custom SDXL prompt
            width: Poster width
            height: Poster height
            
        Returns:
            Complete poster as PIL Image
        """
        logger.info(f"Creating poster for event: {event_data.get('title', 'Unknown')}")
        
        # Generate background
        background = self.generate_background(template, custom_prompt, width, height)
        
        # Add text overlay
        poster = self.add_text_overlay(background, event_data, template)
        
        logger.info("Poster creation completed")
        return poster
    
    def create_session_cards(self, sessions_df, template: str = "tech_conference") -> List[Image.Image]:
        """
        Create individual session cards for each session
        
        Args:
            sessions_df: DataFrame with session information
            template: Design template to use
            
        Returns:
            List of PIL Images (session cards)
        """
        logger.info(f"Creating {len(sessions_df)} session cards")
        
        cards = []
        card_width, card_height = 600, 400  # Smaller format for session cards
        
        for _, session in sessions_df.iterrows():
            event_data = {
                'title': session.get('title', 'Session'),
                'date': f"{session.get('duration', '60')} minutes",
                'venue': f"Speaker: {session.get('speaker', 'TBD')}",
                'details': f"Track: {session.get('track', 'General')}"
            }
            
            # Create session card
            card = self.create_poster(event_data, template, width=card_width, height=card_height)
            cards.append(card)
        
        logger.info(f"Created {len(cards)} session cards")
        return cards
    
    def save_poster(self, poster: Image.Image, filename: str, output_dir: str = "posters") -> str:
        """
        Save poster to file
        
        Args:
            poster: PIL Image to save
            filename: Output filename
            output_dir: Output directory
            
        Returns:
            Full path to saved file
        """
        # Create output directory if it doesn't exist
        Path(output_dir).mkdir(exist_ok=True)
        
        # Ensure filename has extension
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            filename += '.png'
        
        filepath = Path(output_dir) / filename
        poster.save(filepath, format='PNG', quality=95)
        
        logger.info(f"Poster saved to: {filepath}")
        return str(filepath)
    
    def get_available_templates(self) -> List[str]:
        """Return list of available templates"""
        return list(self.templates.keys())
    
    def poster_to_base64(self, poster: Image.Image) -> str:
        """
        Convert poster to base64 string for display in Streamlit
        
        Args:
            poster: PIL Image
            
        Returns:
            Base64 encoded image string
        """
        buffered = io.BytesIO()
        poster.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"

# Example usage and testing functions
def create_sample_event_data() -> Dict:
    """Create sample event data for testing"""
    return {
        'title': 'AI & Future Tech Conference 2025',
        'date': 'October 15-16, 2025',
        'venue': 'Tech Convention Center, Mumbai',
        'details': 'Join industry leaders in AI and emerging technologies'
    }

def test_poster_generation():
    """Test the poster generation system"""
    print("🎨 Testing Poster Generation System...")
    
    # Initialize generator (without SDXL for testing)
    generator = PosterGenerator(use_local_sdxl=False)
    
    # Create sample event data
    event_data = create_sample_event_data()
    
    # Test different templates
    templates = generator.get_available_templates()
    print(f"Available templates: {templates}")
    
    for template in templates:
        print(f"Creating poster with template: {template}")
        poster = generator.create_poster(event_data, template=template)
        
        # Save poster
        filename = f"test_poster_{template}.png"
        filepath = generator.save_poster(poster, filename)
        print(f"Saved: {filepath}")
    
    print("✅ Poster generation test completed!")

if __name__ == "__main__":
    test_poster_generation()