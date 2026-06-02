import { GoogleGenAI } from "@google/genai";

// Initialize Gemini Client
// Note: In a production environment, calls should ideally go through a backend to protect the API KEY,
// or use a proxy. For this client-side demo, we use the process.env directly as instructed.
const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

export interface GroundingChunk {
  // `web` / `maps` fields are echoed straight from the @google/genai response.
  // Library types mark uri/title as optional (different grounding sources omit
  // one or the other), so this interface follows the library shape exactly.
  web?: { uri?: string; title?: string };
  maps?: {
    uri?: string;
    title?: string;
    placeAnswerSources?: { reviewSnippets?: { reviewText?: string }[] }[]
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

    // `toolConfig.googleSearch` was an empty placeholder in earlier @google/genai
    // builds; the current type definition no longer accepts it (and the inner
    // object was always {} anyway, so no behavior is lost by removing it).
    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: prompt,
      config: {
        tools: [{ googleMaps: {} }],
      },
    });

    const candidate = response.candidates?.[0];
    const text = candidate?.content?.parts?.map(p => p.text).join('') || "No insights found.";
    
    // Extract grounding chunks safely. The library's GroundingChunk type is
    // structurally a superset of our local interface (extra inner fields the
    // UI doesn't render), so we cast through `unknown` rather than relax the
    // local type to anyone.
    const groundingChunks = (candidate?.groundingMetadata?.groundingChunks ?? []) as unknown as GroundingChunk[];

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