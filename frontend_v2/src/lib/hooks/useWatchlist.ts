"use client";

import { useState, useEffect } from "react";

export function useWatchlist() {
  const [watchlist, setWatchlist] = useState<string[]>([]);

  // Load from localStorage on mount and listen to updates
  useEffect(() => {
    const loadList = () => {
      try {
        const stored = localStorage.getItem("gridlock_watchlist");
        if (stored) setWatchlist(JSON.parse(stored));
      } catch (e) {
        console.error("Failed to parse watchlist", e);
      }
    };
    
    loadList();
    window.addEventListener('watchlist_updated', loadList);
    return () => window.removeEventListener('watchlist_updated', loadList);
  }, []);

  const toggleWatchlist = (hotspotId: string) => {
    setWatchlist((prev) => {
      let updated;
      if (prev.includes(hotspotId)) {
        updated = prev.filter((id) => id !== hotspotId);
      } else {
        updated = [...prev, hotspotId];
      }
      localStorage.setItem("gridlock_watchlist", JSON.stringify(updated));
      
      // Dispatch a custom event so other components (like LiveMap) can hear the update immediately
      // without needing to refresh the page if they are already mounted
      window.dispatchEvent(new Event('watchlist_updated'));
      
      return updated;
    });
  };

  return { watchlist, toggleWatchlist, setWatchlist };
}
