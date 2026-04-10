/* SPDX-License-Identifier: AGPL-3.0-or-later */
/**
 * Shim for three/webgpu — ClawOS targets WebGL only.
 * three-render-objects imports WebGPURenderer for an optional render path.
 * We alias this module in vite.config.js to avoid the build failure while
 * keeping the WebGL render path fully functional.
 */
export { WebGLRenderer as WebGPURenderer } from 'three'
export * from 'three'
