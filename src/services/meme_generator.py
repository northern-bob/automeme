import requests
from fastmcp import FastMCP, Image
import asyncio
import os
from dotenv import load_dotenv
import json
import logging

# Set up logging at the top of your file
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastMCP
mcp = FastMCP("meme_generator")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

@mcp.tool()
def create_meme(meme_concept: dict) -> str:
    """A tool that YOU (Claude) can and should use to generate memes via the RapidAPI meme generator service.
    You do not need to create or manipulate images directly - this tool handles all image generation.
    
    Note: When calling via MCP, the argument should be wrapped in a dictionary with 'meme_concept' as the key.
    
    Args:
        meme_concept (dict): A dictionary containing the meme configuration with the following keys:
            - template (str): The name of the meme template (e.g., "Distracted-Boyfriend")
            - top_text (str): The text to display at the top of the meme
            - bottom_text (str): The text to display at the bottom of the meme
            - font_size (int, optional): Size of the text font. Defaults to 50
            - font (str, optional): Font family to use. Defaults to "Impact"
    
    Returns:
        str: A success message confirming the meme was generated and saved
        
    Example:
        # When calling via MCP, use this format:
        {
            "meme_concept": {
                "template": "Distracted-Boyfriend",
                "top_text": "Trudeau looking at scandals",
                "bottom_text": "Poilievre watching approval ratings",
                "font_size": 50,  # optional
                "font": "Impact"  # optional
            }
        }
    
    Important: This tool DOES handle all image generation - you do not need to create images yourself.
    Simply call this function with the appropriate text and template, and it will create the meme for you.
    """
    try:
        # Extract the inner dictionary if it's wrapped in a meme_concept key
        if isinstance(meme_concept, dict) and 'meme_concept' in meme_concept:
            meme_concept = meme_concept['meme_concept']

        # Build params with defaults
        params = {
            "meme": meme_concept["template"],
            "top": meme_concept["top_text"],
            "bottom": meme_concept["bottom_text"],
            "font_size": meme_concept.get("font_size", 50),
            "font": meme_concept.get("font", "Impact")
        }
        
        base_url = "https://ronreiter-meme-generator.p.rapidapi.com/meme"
        headers = {
            "X-RapidAPI-Key": os.getenv("RAPID_API_KEY"),
            "X-RapidAPI-Host": "ronreiter-meme-generator.p.rapidapi.com"
        }
            
        response = requests.get(
            base_url,
            headers=headers,
            params=params
        )
        
        # Add detailed error handling for different status codes
        if response.status_code == 500:
            raise Exception("Meme generator service is experiencing internal issues. Please try again later.")
        elif response.status_code == 401:
            raise Exception("Invalid API key. Please check your RAPID_API_KEY environment variable.")
        elif response.status_code == 429:
            raise Exception("Rate limit exceeded. Please try again later.")
            
        response.raise_for_status()
        
        # Verify we got image data
        content_type = response.headers.get('content-type', '')
        if 'image' not in content_type:
            raise Exception(f"Unexpected response type: {content_type}. Expected image data.")
            
        # Save the meme image
        output_path = f"generated_memes/{meme_concept['template']}.jpg"
        os.makedirs("generated_memes", exist_ok=True)
        # Find next available numbered filename
        counter = 1
        base_path = f"generated_memes/{meme_concept['template']}"
        output_path = f"{base_path}.jpg"
        while os.path.exists(output_path):
            output_path = f"{base_path}_{counter}.jpg"
            counter += 1
        with open(output_path, "wb") as f:
            f.write(response.content)
        outcome = f"Successfully generated meme! Saved to: {output_path}"
        logger.info(outcome)
        return outcome
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to generate meme: {str(e)}"
        print(f"Error details: {e.response.text if hasattr(e, 'response') else 'No response text'}")
        raise Exception(error_msg)

@mcp.tool()
def get_meme_templates() -> list:
    """Get a list of all available meme templates from the RapidAPI meme generator service.
    
    Returns:
        list: A list of strings containing the names of available meme templates
        
    Example:
        # Returns something like: ["Distracted-Boyfriend", "Drake-Hotline-Bling", ...]
    """
    try:
        logger.info("Starting get_meme_templates...")
        base_url = "https://ronreiter-meme-generator.p.rapidapi.com/images"
        headers = {
            "X-RapidAPI-Key": os.getenv("RAPID_API_KEY"),
            "X-RapidAPI-Host": "ronreiter-meme-generator.p.rapidapi.com"
        }
            
        logger.info("Making API request...")
        response = requests.get(
            base_url,
            headers=headers,
            timeout=10
        )
        logger.info(f"Got response with status code: {response.status_code}")
        
        # Add detailed error handling for different status codes
        if response.status_code == 500:
            raise Exception("Meme generator service is experiencing internal issues. Please try again later.")
        elif response.status_code == 401:
            raise Exception("Invalid API key. Please check your RAPID_API_KEY environment variable.")
        elif response.status_code == 429:
            raise Exception("Rate limit exceeded. Please try again later.")
            
        response.raise_for_status()
        
        templates = json.loads(response.content)
        logger.info(f"Found {len(templates)} templates")

        logger.info(f"First 5 Templates: {templates[:5]}")
        return templates
            
    except requests.exceptions.Timeout:
        raise Exception("Request timed out while getting meme templates. The service might be slow or unresponsive.")
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to get meme templates: {str(e)}"
        print(f"Error details: {e.response.text if hasattr(e, 'response') else 'No response text'}")
        raise Exception(error_msg)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise

if __name__ == "__main__":
    # Start the FastMCP server
    mcp.run()
    #print(get_meme_templates())
