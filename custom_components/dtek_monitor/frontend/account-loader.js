/* HA installs its custom-element registry during startup. Registering cards
 * before the host exists can leave their dependencies in the old registry. */
function loadWhenReady() {
  if (!customElements.get("home-assistant")) {
    window.setTimeout(loadWhenReady, 100);
    return;
  }
  Promise.all([
    import("./account-workspace-card.js?v=2.0.0-rc4"),
    import("./outage-card.js?v=2.0.0-rc4"),
  ]).catch(() => {
    // Report only a generic loading failure, never private state.
    console.error("DTEK cards could not load. Reload the Home Assistant page.");
  });
}
loadWhenReady();
