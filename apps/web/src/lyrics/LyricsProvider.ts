export interface LyricLine {
  index: number;
  startMs: number | null;
  text: string;
}

/** Lyrics are never stored in the DB; a licensed provider supplies them at runtime. */
export interface LyricsProvider {
  getLyrics(args: { isrc?: string; appleMusicTrackId?: string }): Promise<LyricLine[]>;
}

export const stubLyricsProvider: LyricsProvider = {
  async getLyrics() {
    return [];
  },
};
