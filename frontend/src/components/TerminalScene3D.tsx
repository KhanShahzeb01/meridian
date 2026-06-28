"use client";

import { useEffect, useRef } from "react";

const REST_X = 12;
const REST_Y = -22;
const MAX_TILT = 20;

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

export function TerminalScene3D() {
  const visualRef = useRef<HTMLDivElement>(null);
  const rigRef = useRef<HTMLDivElement>(null);
  const shadowRef = useRef<HTMLDivElement>(null);
  const ambientRef = useRef<HTMLDivElement>(null);
  const glareRef = useRef<HTMLDivElement>(null);
  const auraRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const visual = visualRef.current;
    const rig = rigRef.current;
    if (!visual || !rig) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      rig.style.transform = `rotateX(${REST_X}deg) rotateY(${REST_Y}deg)`;
      return;
    }

    let currentX = REST_X;
    let currentY = REST_Y;
    let targetX = REST_X;
    let targetY = REST_Y;
    let glareX = 28;
    let glareY = 22;
    let targetGlareX = 28;
    let targetGlareY = 22;
    let frame = 0;

    const tick = () => {
      currentX = lerp(currentX, targetX, 0.085);
      currentY = lerp(currentY, targetY, 0.085);
      glareX = lerp(glareX, targetGlareX, 0.12);
      glareY = lerp(glareY, targetGlareY, 0.12);

      const lift =
        10 +
        Math.abs(currentY - REST_Y) * 0.35 +
        Math.abs(currentX - REST_X) * 0.2;
      rig.style.transform = `rotateX(${currentX.toFixed(2)}deg) rotateY(${currentY.toFixed(2)}deg) translateZ(${lift.toFixed(1)}px)`;

      if (auraRef.current) {
        const auraShiftX = (currentY - REST_Y) * 1.4;
        const auraShiftY = (currentX - REST_X) * -1.1;
        auraRef.current.style.transform = `translate3d(${auraShiftX.toFixed(1)}px, ${auraShiftY.toFixed(1)}px, -90px) scale(1.02)`;
      }

      if (glareRef.current) {
        glareRef.current.style.background = `radial-gradient(circle at ${glareX.toFixed(1)}% ${glareY.toFixed(1)}%, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0.04) 22%, transparent 54%)`;
      }

      if (shadowRef.current) {
        const offsetX = ((currentY - REST_Y) / MAX_TILT) * 22;
        const offsetY = ((currentX - REST_X) / MAX_TILT) * 14;
        const scale = 1 + (Math.abs(currentY - REST_Y) / MAX_TILT) * 0.1;
        shadowRef.current.style.transform = `translateX(calc(-50% + ${offsetX.toFixed(1)}px)) translateY(${offsetY.toFixed(1)}px) scale(${scale.toFixed(3)})`;
      }

      if (ambientRef.current) {
        const glowX = ((currentY - REST_Y) / MAX_TILT) * 18;
        const glowOpacity = 0.75 + (Math.abs(currentX - REST_X) / MAX_TILT) * 0.25;
        ambientRef.current.style.transform = `translateX(calc(-50% + ${glowX.toFixed(1)}px)) translateZ(-60px)`;
        ambientRef.current.style.opacity = glowOpacity.toFixed(2);
      }

      frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);

    const onMove = (e: MouseEvent) => {
      const rect = visual.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      targetY = REST_Y + x * MAX_TILT * 2.4;
      targetX = REST_X - y * MAX_TILT * 2.4;

      if (cardRef.current) {
        const cardRect = cardRef.current.getBoundingClientRect();
        targetGlareX = ((e.clientX - cardRect.left) / cardRect.width) * 100;
        targetGlareY = ((e.clientY - cardRect.top) / cardRect.height) * 100;
      }
    };

    const onLeave = () => {
      targetX = REST_X;
      targetY = REST_Y;
      targetGlareX = 28;
      targetGlareY = 22;
    };

    visual.addEventListener("mousemove", onMove);
    visual.addEventListener("mouseleave", onLeave);

    return () => {
      cancelAnimationFrame(frame);
      visual.removeEventListener("mousemove", onMove);
      visual.removeEventListener("mouseleave", onLeave);
    };
  }, []);

  return (
    <div className="hero-visual fade-in-up fade-in-up-delay-2" ref={visualRef}>
      <div className="terminal-scene">
        <div className="terminal-rig" ref={rigRef}>
          <div className="terminal-aura" ref={auraRef} aria-hidden="true" />
          <div className="terminal-stack">
            <div className="terminal-chassis">
              <div className="terminal-chassis__edge terminal-chassis__edge--left" aria-hidden="true" />
              <div className="terminal-chassis__edge terminal-chassis__edge--right" aria-hidden="true" />
              <div className="terminal-chassis__lip" aria-hidden="true" />
              <div className="terminal-bezel">
                <div className="terminal-card" ref={cardRef}>
                  <div className="terminal-card__chrome">
                    <span className="dot dot-red" />
                    <span className="dot dot-yellow" />
                    <span className="dot dot-green" />
                    <span className="terminal-card__title">meridian — terminal</span>
                  </div>
                  <pre className="terminal-card__body">
                    <span className="terminal-prompt">meridian@general ~ </span>
                    <span className="terminal-cmd">/quote AAPL</span>
                    {"\n"}
                    <span className="terminal-dim">  Apple Inc. · $227.52 (+1.24%) · P/E 35.2</span>
                    {"\n\n"}
                    <span className="terminal-prompt">meridian@general ~ </span>
                    <span className="terminal-cmd">/consensus NVDA</span>
                    {"\n"}
                    <span className="terminal-dim">  Panel vote · BUY 4 · HOLD 2 · SELL 0</span>
                    {"\n\n"}
                    <span className="terminal-prompt">meridian@general ~ </span>
                    <span className="terminal-cmd">/ask buffett TSLA</span>
                    {"\n"}
                    <span className="terminal-dim">  Streaming analysis…</span>
                    <span className="terminal-cursor" aria-hidden="true" />
                  </pre>
                  <div className="terminal-card__scanlines" aria-hidden="true" />
                  <div className="terminal-card__glare" ref={glareRef} aria-hidden="true" />
                </div>
              </div>
              <div className="terminal-keyboard" aria-hidden="true">
                <span />
                <span />
                <span />
                <span />
                <span />
                <span className="terminal-keyboard__space" />
                <span />
                <span />
                <span />
              </div>
            </div>
          </div>
        </div>
        <div className="terminal-scene__shadow" ref={shadowRef} aria-hidden="true" />
        <div className="terminal-scene__glow" ref={ambientRef} aria-hidden="true" />
      </div>
      <p className="drag-hint">
        <span className="drag-hint__pulse" aria-hidden="true" />
        Move your cursor — terminal tilts with you
      </p>
    </div>
  );
}
