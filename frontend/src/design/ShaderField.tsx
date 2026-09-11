import { useEffect, useRef } from "react";
import { cn } from "./ui/cn";

/**
 * A slow, dark, domain-warped noise field, drawn behind an entry screen's
 * headline.
 *
 * Written directly against WebGL2 rather than through a scene graph: this is
 * one fullscreen triangle pair and one fragment shader, so a 3D library would
 * be ~150KB gzipped for geometry we do not have. It also keeps the offline
 * guarantee in `index.css` intact — nothing is fetched.
 *
 * It is deliberately confined. Motion behind a 500-row table makes the table
 * harder to read, so this renders in a band behind a title and its headline
 * figures and fades out before the data starts. Everything above it is opaque.
 *
 * Costs are capped on purpose:
 *  - half-resolution buffer, upscaled by the compositor
 *  - ~30fps, not 60
 *  - paused when the tab is hidden or the band is scrolled out of view
 *  - a single static frame under `prefers-reduced-motion`
 *  - silently absent if WebGL2 is unavailable; the CSS wash behind it stands
 *    on its own, so there is nothing to fall back to
 */

const VERT = `#version 300 es
in vec2 a_pos;
out vec2 v_uv;
void main() {
  v_uv = a_pos * 0.5 + 0.5;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}`;

/**
 * Value-noise fbm, warped by another fbm, then used to mix three colours.
 *
 * Value noise rather than simplex: it is a third of the instructions, and at
 * this scale and speed the difference is not visible. `u_aspect` keeps the
 * cells square in a wide, short band.
 */
const FRAG = `#version 300 es
precision mediump float;

in vec2 v_uv;
out vec4 outColor;

uniform float u_time;
uniform float u_aspect;
uniform vec3 u_c0;
uniform vec3 u_c1;
uniform vec3 u_c2;
uniform float u_intensity;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(hash(i + vec2(0.0, 0.0)), hash(i + vec2(1.0, 0.0)), u.x),
    mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
    u.y
  );
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 4; i++) {
    v += a * noise(p);
    p *= 2.02;
    a *= 0.5;
  }
  return v;
}

void main() {
  vec2 uv = v_uv;
  uv.x *= u_aspect;

  float t = u_time * 0.035;

  // Warp the sampling coordinates with a second field: this is what turns
  // layered noise into something that reads as flow rather than as static.
  vec2 q = vec2(fbm(uv * 1.6 + vec2(t, -t * 0.7)), fbm(uv * 1.6 + vec2(4.7, 9.2) + t * 0.8));
  float f = fbm(uv * 2.1 + q * 1.7 + vec2(-t * 0.5, t * 0.35));

  vec3 col = mix(u_c0, u_c1, clamp(f * 1.35, 0.0, 1.0));
  col = mix(col, u_c2, clamp(pow(f, 3.0) * 1.6, 0.0, 1.0));

  // Fade to nothing at the bottom and the edges so the band dissolves into
  // the page instead of ending on a line.
  float vign = smoothstep(0.0, 0.45, 1.0 - v_uv.y);
  float sides = smoothstep(0.0, 0.22, v_uv.x) * smoothstep(0.0, 0.22, 1.0 - v_uv.x);

  outColor = vec4(col, vign * sides * u_intensity);
}`;

function compile(gl: WebGL2RenderingContext, type: number, src: string): WebGLShader | null {
  const sh = gl.createShader(type);
  if (sh === null) return null;
  gl.shaderSource(sh, src);
  gl.compileShader(sh);
  if (gl.getShaderParameter(sh, gl.COMPILE_STATUS) !== true) {
    gl.deleteShader(sh);
    return null;
  }
  return sh;
}

/** Reads a token colour off the document and returns it as 0..1 RGB. */
function tokenRgb(name: string, fallback: [number, number, number]): [number, number, number] {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const hex = /^#([0-9a-f]{6})$/i.exec(raw);
  if (hex === null) return fallback;
  const n = parseInt(hex[1] ?? "", 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

export function ShaderField({ className }: { className?: string }): React.JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas === null) return;

    const gl = canvas.getContext("webgl2", {
      alpha: true,
      antialias: false,
      depth: false,
      stencil: false,
      powerPreference: "low-power",
    });
    if (gl === null) return;

    const vs = compile(gl, gl.VERTEX_SHADER, VERT);
    const fs = compile(gl, gl.FRAGMENT_SHADER, FRAG);
    if (vs === null || fs === null) return;

    const prog = gl.createProgram();
    if (prog === null) return;
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    if (gl.getProgramParameter(prog, gl.LINK_STATUS) !== true) return;
    gl.useProgram(prog);

    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 3, -1, -1, 3]),
      gl.STATIC_DRAW,
    );
    const loc = gl.getAttribLocation(prog, "a_pos");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

    const uTime = gl.getUniformLocation(prog, "u_time");
    const uAspect = gl.getUniformLocation(prog, "u_aspect");
    const uIntensity = gl.getUniformLocation(prog, "u_intensity");

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    /**
     * Colours come from the live tokens, so the field follows the theme
     * instead of hard-coding a palette that would drift out of sync.
     */
    const applyPalette = (): void => {
      const light = document.documentElement.dataset["theme"] === "light";
      const c0 = tokenRgb(light ? "--surface-0" : "--surface-0", light ? [0.93, 0.95, 0.97] : [0.02, 0.04, 0.08]);
      const c1 = tokenRgb("--accent", light ? [0.18, 0.29, 0.88] : [0.27, 0.4, 0.94]);
      const c2 = tokenRgb("--info", light ? [0.02, 0.46, 0.54] : [0.25, 0.82, 0.88]);
      gl.uniform3f(gl.getUniformLocation(prog, "u_c0"), c0[0], c0[1], c0[2]);
      gl.uniform3f(gl.getUniformLocation(prog, "u_c1"), c1[0], c1[1], c1[2]);
      gl.uniform3f(gl.getUniformLocation(prog, "u_c2"), c2[0], c2[1], c2[2]);
      // The light theme needs far less of it: the same alpha that reads as a
      // glow on near-black reads as dirt on paper.
      gl.uniform1f(uIntensity, light ? 0.2 : 0.45);
    };

    // Half resolution. At this blur level the upscale is invisible and it
    // quarters the fragment work.
    const resize = (): void => {
      const rect = canvas.getBoundingClientRect();
      const scale = Math.min(window.devicePixelRatio || 1, 2) * 0.5;
      const w = Math.max(1, Math.round(rect.width * scale));
      const h = Math.max(1, Math.round(rect.height * scale));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
        gl.viewport(0, 0, w, h);
      }
      gl.uniform1f(uAspect, rect.height > 0 ? rect.width / rect.height : 1);
    };

    const draw = (seconds: number): void => {
      gl.uniform1f(uTime, seconds);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    };

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    applyPalette();
    resize();

    let raf = 0;
    let last = 0;
    let visible = true;
    const FRAME_MS = 1000 / 30;

    const loop = (now: number): void => {
      raf = requestAnimationFrame(loop);
      if (!visible || now - last < FRAME_MS) return;
      last = now;
      draw(now / 1000);
    };

    const start = (): void => {
      if (reduced.matches) {
        // One frame, held. The composition still reads; nothing moves.
        resize();
        draw(12);
        return;
      }
      if (raf === 0) raf = requestAnimationFrame(loop);
    };
    const stop = (): void => {
      if (raf !== 0) {
        cancelAnimationFrame(raf);
        raf = 0;
      }
    };

    const onVisibility = (): void => {
      if (document.hidden) stop();
      else start();
    };
    const onResize = (): void => {
      resize();
      if (reduced.matches) draw(12);
    };
    // Scrolled out of view costs nothing.
    const io = new IntersectionObserver(
      (entries) => {
        visible = entries[0]?.isIntersecting ?? true;
        if (visible) start();
        else stop();
      },
      { rootMargin: "120px" },
    );
    io.observe(canvas);

    // The palette changes when the theme is toggled.
    const themeObserver = new MutationObserver(() => {
      applyPalette();
      if (reduced.matches) draw(12);
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    const onReducedChange = (): void => {
      stop();
      start();
    };

    window.addEventListener("resize", onResize);
    document.addEventListener("visibilitychange", onVisibility);
    reduced.addEventListener("change", onReducedChange);
    start();

    return () => {
      stop();
      io.disconnect();
      themeObserver.disconnect();
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
      reduced.removeEventListener("change", onReducedChange);
      gl.deleteProgram(prog);
      gl.deleteShader(vs);
      gl.deleteShader(fs);
      gl.deleteBuffer(buf);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      data-testid="shader-field"
      className={cn("pointer-events-none absolute inset-0 h-full w-full", className)}
    />
  );
}
