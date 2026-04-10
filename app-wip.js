const trackerCursor = document.getElementById("tracker-cursor");
const isTouchDevice = window.matchMedia("(hover: none), (pointer: coarse)").matches;

const cursorState = {
  currentX: window.innerWidth / 2,
  currentY: window.innerHeight / 2,
  targetX: window.innerWidth / 2,
  targetY: window.innerHeight / 2
};

function animateCursor() {
  if (!trackerCursor) {
    return;
  }

  cursorState.currentX += (cursorState.targetX - cursorState.currentX) * 0.38;
  cursorState.currentY += (cursorState.targetY - cursorState.currentY) * 0.38;
  trackerCursor.style.transform = `translate(${cursorState.currentX}px, ${cursorState.currentY}px)`;
  window.requestAnimationFrame(animateCursor);
}

if (!isTouchDevice && trackerCursor) {
  window.addEventListener("mousemove", (event) => {
    cursorState.targetX = event.clientX;
    cursorState.targetY = event.clientY;
    trackerCursor.classList.add("is-visible");
  });

  window.addEventListener("mouseleave", () => {
    trackerCursor.classList.remove("is-visible");
  });

  animateCursor();
}
