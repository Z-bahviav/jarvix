"""Jarvis-style voice HUD (inspired by interactive assistant UIs with orb + state rings)."""

from __future__ import annotations

VOICE_HUD_CSS = """
.jarvis-hud {
  background: linear-gradient(160deg, #00060a 0%, #010d14 45%, #001018 100%);
  border: 1px solid #0d3347;
  border-radius: 12px;
  color: #8ffcff;
}
.voice-orb-wrap {
  position: relative;
  width: 132px;
  height: 132px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.voice-orb-core {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #00d4ff, #007a99 55%, #001f2e 100%);
  box-shadow: 0 0 24px rgba(0, 212, 255, 0.35);
  z-index: 3;
  transition: transform 0.2s ease, box-shadow 0.3s ease;
}
.voice-orb-wrap:hover .voice-orb-core {
  transform: scale(1.04);
}
.voice-ring {
  position: absolute;
  border-radius: 50%;
  border: 2px solid rgba(0, 255, 136, 0.35);
  opacity: 0;
  pointer-events: none;
}
.voice-orb-wrap.listening .voice-ring.r1 {
  width: 88px; height: 88px; opacity: 1;
  animation: jarvis-ring 2.2s ease-out infinite;
}
.voice-orb-wrap.listening .voice-ring.r2 {
  width: 104px; height: 104px; opacity: 0.7;
  animation: jarvis-ring 2.2s ease-out infinite 0.5s;
}
.voice-orb-wrap.listening .voice-ring.r3 {
  width: 120px; height: 120px; opacity: 0.45;
  animation: jarvis-ring 2.2s ease-out infinite 1s;
}
.voice-orb-wrap.listening .voice-orb-core {
  box-shadow: 0 0 32px rgba(0, 255, 136, 0.45);
  background: radial-gradient(circle at 35% 30%, #00ff88, #00aa55 50%, #001f2e 100%);
}
.voice-orb-wrap.thinking .voice-orb-core {
  animation: jarvis-think-spin 1.8s linear infinite;
  box-shadow: 0 0 28px rgba(0, 212, 255, 0.55);
}
.voice-orb-wrap.speaking .voice-orb-core {
  background: radial-gradient(circle at 35% 30%, #ffcc00, #ff6b00 55%, #331400 100%);
  box-shadow: 0 0 34px rgba(255, 107, 0, 0.55);
  animation: jarvis-speak-pulse 0.55s ease-in-out infinite alternate;
}
.voice-orb-wrap.reconnecting .voice-orb-core {
  opacity: 0.65;
  animation: jarvis-speak-pulse 1.1s ease-in-out infinite;
}
.voice-orb-wrap.active-session .voice-orb-core {
  outline: 2px solid #00ff88;
  outline-offset: 3px;
}
@keyframes jarvis-ring {
  0% { transform: scale(0.75); opacity: 0.9; }
  100% { transform: scale(1.15); opacity: 0; }
}
@keyframes jarvis-think-spin {
  0% { filter: hue-rotate(0deg); }
  100% { filter: hue-rotate(360deg); }
}
@keyframes jarvis-speak-pulse {
  from { transform: scale(1); }
  to { transform: scale(1.08); }
}
.hud-state-title {
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #d8f8ff;
}
.hud-state-detail {
  font-size: 0.85rem;
  color: #5ab8cc;
  min-height: 1.25rem;
}
.level-bar {
  width: 6px;
  height: 28px;
  border-radius: 3px;
  background: #0d3347;
  transform-origin: bottom;
  transition: transform 0.08s ease, background 0.08s ease;
}
.level-bar.on {
  background: linear-gradient(180deg, #00ff88, #00d4ff);
}
.live-transcript-panel {
  border-left: 4px solid #00d4ff;
  background: linear-gradient(90deg, #001018 0%, #010d14 100%);
  color: #d8f8ff;
}
"""
