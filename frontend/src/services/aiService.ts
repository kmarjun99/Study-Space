import { GoogleGenAI } from "@google/genai";

// Initialize Gemini Client
// Note: In a production environment, calls should ideally go through a backend to protect the API KEY,
// or use a proxy. For this client-side demo, we use the process.env directly as instructed.
const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

export interface GroundingChunk {
  web?: { uri: string; title: string };
  maps?: { 
    uri: string; 
    title: string;
    placeAnswerSources?: { reviewSnippets?: { reviewText: string }[] }[] 
  };
}

export interface AIResponse {
  text: string;
  groundingChunks: GroundingChunk[];
}

export const getLocationInsights = async (
  query: string, 
  contextAddress?: string
): Promise<AIResponse> => {
  try {
    let prompt = query;
    
    // If we are looking at a specific venue, prepend context
    if (contextAddress) {
      prompt = `Regarding the location "${contextAddress}": ${query}`;
    }

    // Get user location for "near me" queries
    let userLocation = undefined;
    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 });
      });
      userLocation = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude
      };
    } catch (e) {
      console.warn("Location access denied or timed out, proceeding without user location.");
    }

    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: prompt,
      config: {
        tools: [{ googleMaps: {} }],
        toolConfig: userLocation ? {
          googleSearch: { // googleMaps tool uses retrievalConfig inside toolConfig, sometimes shared naming conventions apply
             // Note: The SDK structure for Maps grounding specifically usually infers location or takes it in prompt,
             // but retrievalConfig is the standard way to pass lat/long for grounding tools.
          }
        } : undefined
      },
    });

    const candidate = response.candidates?.[0];
    const text = candidate?.content?.parts?.map(p => p.text).join('') || "No insights found.";
    
    // Extract grounding chunks safely
    const groundingChunks = candidate?.groundingMetadata?.groundingChunks || [];

    return {
      text,
      groundingChunks
    };

  } catch (error) {
    console.error("AI Service Error:", error);
    return {
      text: "I'm having trouble connecting to Google Maps right now. Please try again later.",
      groundingChunks: []
    };
  }
};