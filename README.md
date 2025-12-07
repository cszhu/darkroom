# Darkroom - AI-Powered Photo Restoration

A web application that uses AI to restore, enhance, and animate old physical photographs. Built with FastAPI and Gemini AI.

## Features

- **AI-Powered Photo Extraction**: Automatically detects and crops physical photographs from images using Gemini Vision
- **Historical Metadata Extraction**: Extracts rich metadata including estimated year, clothing styles, socioeconomic insights, and lifestyle information
- **Wikipedia Integration**: Fetches historical context and related Wikipedia pages based on location and era
- **Photo Restoration**: Restores damaged photos, removes scratches and fading, and optionally colorizes black & white images
- **Video Generation**: Creates cinematic videos that bring restored photos to life using Veo 3.1
- **Educational Content**: Provides historical context connecting visual elements to the era

## Tech Stack

- **Backend**: FastAPI, Python 3.11+
- **AI**: Google Gemini 2.0 Flash (metadata extraction), Gemini 3 Pro Image Preview (restoration), Veo 3.1 (video generation)
- **Image Processing**: Pillow (PIL)
- **Frontend**: Vanilla HTML/CSS/JavaScript with Tailwind CSS
- **APIs**: Wikipedia REST API (free, no signup required)

## Setup

### Prerequisites

- Python 3.11 or higher
- A Google Gemini API key ([Get one here](https://makersuite.google.com/app/apikey))

### Installation

1. **Clone the repository:**

   ```bash
   git clone <url>
   cd darkroom
   ```

2. **Create a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**

   ```bash
   cp .env.example .env
   # Edit .env and add your GEMINI_API_KEY
   ```

5. **Run the application:**

   ```bash
   uvicorn app.main:app --reload
   ```

6. **Open your browser:**
   Navigate to `http://localhost:8000`

## Project Structure

```
darkroom/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Configuration and initialization
│   ├── routes.py            # API endpoints
│   ├── gemini/
│   │   ├── analysis.py      # Metadata extraction with Gemini
│   │   └── restoration.py   # Photo restoration and video generation with Gemini
│   ├── image_processing/
│   │   ├── bounding_box.py  # Bounding box normalization
│   │   ├── cropping.py      # Image cropping utilities
│   │   └── visualization.py # Debug visualization (optional)
│   ├── wikipedia/
│   │   └── api.py          # Wikipedia API integration
│   └── utils/
│       └── parsing.py       # JSON parsing utilities
├── static/
│   └── index.html          # Frontend UI
├── uploads/                # Temporary storage for uploaded images
├── outputs/                # Storage for processed images
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
└── README.md              # This file
```

## API Endpoints

- `GET /` - Serve the main HTML page
- `POST /api/process` - Process an uploaded image
  - Parameters:
    - `file`: Image file (multipart/form-data)
    - `location`: Optional location where photo was taken
    - `historical_context`: Optional additional context
    - `colorize`: Whether to colorize ("true" or "false")
- `GET /uploads/{filename}` - Serve uploaded files
- `GET /outputs/{filename}` - Serve processed output files

## Usage

1. Upload a photo of an old physical photograph (can be a photo of a photo)
2. Optionally provide location and historical context
3. Choose whether to colorize the restored image
4. View the results:
   - Original uploaded image
   - Extracted/cropped photograph
   - Restored and enhanced version
   - Historical metadata and analysis
   - Related Wikipedia links

## How It Works

1. **Metadata Extraction**: Gemini 2.0 Flash processes the uploaded image to detect the physical photograph boundaries and extract historical metadata
2. **Wikipedia Context**: If a location is provided, the app fetches relevant Wikipedia pages for historical context
3. **Cropping**: The detected bounding box is used to crop the physical photograph from the image
4. **Restoration**: Gemini 3 Pro Image Preview restores the photo, removes damage, and optionally colorizes it with historically accurate tones
5. **Video Generation**: Veo 3.1 creates cinematic videos bringing restored photos to life (optional)
6. **Display**: All results and metadata are displayed in the web interface

## Environment Variables

Required:

- `GEMINI_API_KEY`: Your Google Gemini API key

See `.env.example` for the template.

## License

See LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
