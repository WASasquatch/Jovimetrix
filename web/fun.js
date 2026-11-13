/**
 * Small visual effects: rising bubbles on a canvas, and a flashing background on an element.
 */

/**
 * Animate rising bubbles across a canvas until the returned function is called.
 *
 * @param {HTMLCanvasElement} canvas - The canvas to draw on; it is sized to its own box.
 * @returns {() => void} Stops the animation and clears the canvas.
 */
export function bubbles(canvas) {
    const context = canvas.getContext("2d");
    const particles = [];
    let alive = true;

    const fit = () => {
        canvas.width = canvas.clientWidth || window.innerWidth;
        canvas.height = canvas.clientHeight || window.innerHeight;
    };
    fit();

    const spawn = () => ({
        x: Math.random() * canvas.width,
        y: canvas.height + 30,
        radius: 4 + Math.random() * 26,
        dx: (Math.random() - 0.5) * 2.5,
        dy: 2 + Math.random() * 3,
        hue: 25 + Math.random() * 250,
        sat: 85 + Math.random() * 15,
        val: 35 + Math.random() * 20,
    });

    const frame = () => {
        if (!alive) {
            context.clearRect(0, 0, canvas.width, canvas.height);
            return;
        }
        context.clearRect(0, 0, canvas.width, canvas.height);
        if (Math.random() > 0.5 && particles.length < 200) {
            particles.push(spawn());
        }
        for (let i = particles.length - 1; i >= 0; i--) {
            const p = particles[i];
            p.x += p.dx + (Math.random() - 0.5) * 0.5;
            p.y -= p.dy + (Math.random() - 0.5) * 1.5;
            if (p.y < -p.radius || p.x < -p.radius || p.x > canvas.width + p.radius) {
                particles.splice(i, 1);
                continue;
            }
            context.beginPath();
            context.arc(p.x, p.y, p.radius, 0, 2 * Math.PI);
            context.strokeStyle = `hsl(${p.hue} ${p.sat}% ${p.val}%)`;
            context.stroke();
            const gradient = context.createRadialGradient(p.x, p.y, 1, p.x + 0.5, p.y + 0.5, p.radius);
            gradient.addColorStop(0.3, "rgba(255, 255, 255, 0.3)");
            gradient.addColorStop(0.95, "#E7FEFF7F");
            context.fillStyle = gradient;
            context.fill();
        }
        requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
    window.addEventListener("resize", fit);

    return () => {
        alive = false;
        window.removeEventListener("resize", fit);
    };
}

const flashing = new WeakSet();

/**
 * Flash an element's background colour a few times.
 *
 * @param {HTMLElement} element - The element.
 * @param {number} duration - Milliseconds per flash.
 * @param {number} flashCount - Number of flashes.
 * @param {string} [color] - Flash colour.
 */
export async function flashBackgroundColor(element, duration, flashCount, color = "red") {
    if (!element || flashing.has(element)) {
        return;
    }
    flashing.add(element);
    const originalColor = element.style.backgroundColor;
    for (let i = 0; i < flashCount; i++) {
        element.style.backgroundColor = color;
        await new Promise(resolve => setTimeout(resolve, duration / 2));
        element.style.backgroundColor = originalColor;
        await new Promise(resolve => setTimeout(resolve, duration / 2));
    }
    flashing.delete(element);
}
