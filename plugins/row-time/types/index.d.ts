declare module 'claude-code' {
  interface PluginState {
    'row-time': {
      /** The session's transcript file, held for a later load of the mod, which hears no classic.SessionStart. */
      transcript: string
    }
  }
}
