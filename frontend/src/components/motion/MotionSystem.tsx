"use client";

import React, { useEffect, useRef, useState } from "react";

/**
 * SSR-safe hook to detect and react to `prefers-reduced-motion: reduce`.
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mediaQuery.matches);

    const handler = (event: MediaQueryListEvent) => {
      setReduced(event.matches);
    };

    mediaQuery.addEventListener("change", handler);
    return () => mediaQuery.removeEventListener("change", handler);
  }, []);

  return reduced;
}

interface RevealSectionProps {
  children: React.ReactNode;
  className?: string;
  delayMs?: number;
  yOffset?: number;
  threshold?: number;
  as?: "div" | "section" | "article" | "li";
}

/**
 * Scroll-triggered reveal component using IntersectionObserver.
 * Respects `prefers-reduced-motion` by rendering immediately without transform.
 */
export function RevealSection({
  children,
  className = "",
  delayMs = 0,
  yOffset = 18,
  threshold = 0.12,
  as: Tag = "div",
}: RevealSectionProps) {
  const reducedMotion = useReducedMotion();
  const ref = useRef<HTMLElement | null>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (reducedMotion) {
      setIsVisible(true);
      return;
    }

    const node = ref.current;
    if (!node) return;

    if (typeof IntersectionObserver === "undefined") {
      setIsVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible(true);
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold, rootMargin: "0px 0px -32px 0px" }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [reducedMotion, threshold]);

  const style: React.CSSProperties = reducedMotion
    ? {}
    : {
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? "translate3d(0, 0, 0)" : `translate3d(0, ${yOffset}px, 0)`,
        transitionProperty: "opacity, transform",
        transitionDuration: "560ms",
        transitionTimingFunction: "cubic-bezier(0.22, 1, 0.36, 1)",
        transitionDelay: `${delayMs}ms`,
      };

  return (
    <Tag
      ref={ref as any}
      className={className}
      style={style}
    >
      {children}
    </Tag>
  );
}

interface AnimatedCounterProps {
  value: number;
  durationMs?: number;
  className?: string;
  format?: (val: number) => string;
}

/**
 * Animates a numeric metric once when its value first arrives or changes from backend data.
 * Never re-triggers on hover or unrelated component re-renders.
 */
export function AnimatedCounter({
  value,
  durationMs = 650,
  className = "",
  format,
}: AnimatedCounterProps) {
  const reducedMotion = useReducedMotion();
  const [displayValue, setDisplayValue] = useState<number>(value);
  const previousTargetRef = useRef<number | null>(null);

  useEffect(() => {
    if (reducedMotion || value === 0) {
      setDisplayValue(value);
      previousTargetRef.current = value;
      return;
    }

    if (previousTargetRef.current === value) {
      return;
    }

    const startValue = previousTargetRef.current ?? 0;
    previousTargetRef.current = value;

    let animationFrameId: number;
    const startTime = performance.now();

    const step = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / durationMs, 1);
      // Exponential ease-out
      const eased = 1 - Math.pow(1 - progress, 4);
      const current = Math.round(startValue + (value - startValue) * eased);
      setDisplayValue(current);

      if (progress < 1) {
        animationFrameId = requestAnimationFrame(step);
      } else {
        setDisplayValue(value);
      }
    };

    animationFrameId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(animationFrameId);
  }, [value, durationMs, reducedMotion]);

  const formatted = format ? format(displayValue) : displayValue.toLocaleString();

  return <span className={`tabular-nums ${className}`}>{formatted}</span>;
}

interface SubtleParallaxProps {
  children: React.ReactNode;
  maxShiftPx?: number;
  className?: string;
}

/**
 * Restrained scroll-linked parallax wrapper for decorative schematic layers.
 * Automatically disabled on mobile viewports (<768px) and under `prefers-reduced-motion`.
 */
export function SubtleParallax({
  children,
  maxShiftPx = 18,
  className = "",
}: SubtleParallaxProps) {
  const reducedMotion = useReducedMotion();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [offsetY, setOffsetY] = useState(0);

  useEffect(() => {
    if (reducedMotion || typeof window === "undefined") {
      setOffsetY(0);
      return;
    }

    let ticking = false;

    const updateParallax = () => {
      ticking = false;
      if (window.innerWidth < 768 || !containerRef.current) {
        setOffsetY(0);
        return;
      }
      const rect = containerRef.current.getBoundingClientRect();
      const viewportHeight = window.innerHeight || 1;
      const centerProgress = (rect.top + rect.height / 2 - viewportHeight / 2) / (viewportHeight / 2);
      const clamped = Math.max(-1, Math.min(1, centerProgress));
      setOffsetY(Math.round(clamped * -maxShiftPx));
    };

    const onScroll = () => {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(updateParallax);
      }
    };

    updateParallax();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });

    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [reducedMotion, maxShiftPx]);

  return (
    <div
      ref={containerRef}
      className={className}
      style={
        reducedMotion
          ? undefined
          : {
              transform: `translate3d(0, ${offsetY}px, 0)`,
              transition: "transform 120ms cubic-bezier(0.22, 1, 0.36, 1)",
            }
      }
    >
      {children}
    </div>
  );
}
