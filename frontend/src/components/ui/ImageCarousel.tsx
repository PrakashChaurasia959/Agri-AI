import { useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/utils/cn';

const images = [
  {
    src: '/images/agriculture/carousel-1.jpg',
    alt: 'Lush green agricultural fields',
  },
  {
    src: '/images/agriculture/carousel-2.jpg',
    alt: 'Farmers working in wheat field',
  },
  {
    src: '/images/agriculture/carousel-3.jpg',
    alt: 'Rice plantation with modern irrigation',
  },
  {
    src: '/images/agriculture/carousel-4.jpg',
    alt: 'Healthy growing crops',
  },
];

export function ImageCarousel() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    if (isPaused) return;
    const interval = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % images.length);
    }, 4500);
    return () => clearInterval(interval);
  }, [isPaused]);

  const goToPrevious = () => {
    setCurrentIndex((prev) => (prev - 1 + images.length) % images.length);
  };

  const goToNext = () => {
    setCurrentIndex((prev) => (prev + 1) % images.length);
  };

  return (
    <div
      className="relative w-full h-full overflow-hidden rounded-3xl shadow-2xl"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      role="region"
      aria-label="Agricultural image carousel"
    >
      {images.map((image, index) => (
        <div
          key={index}
          className={cn(
            'absolute inset-0 transition-opacity duration-1000 ease-in-out',
            index === currentIndex ? 'opacity-100' : 'opacity-0',
          )}
        >
          <img
            src={image.src}
            alt={image.alt}
            className="w-full h-full object-cover"
            // All slides are part of the auto-advancing carousel and are
            // technically in the viewport, but with `opacity-0`. Chromium's
            // lazy-loading heuristic refuses to fetch them in that state, so
            // the carousel would fade to a blank slide. Eager-load all four
            // (they are local assets) and let the browser decode async.
            loading="eager"
            decoding="async"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent" />
        </div>
      ))}

      <button
        onClick={goToPrevious}
        className="absolute left-4 top-1/2 -translate-y-1/2 z-10 rounded-full bg-white/90 p-2 shadow-lg transition hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
        aria-label="Previous slide"
      >
        <ChevronLeft className="h-6 w-6 text-gray-900" />
      </button>

      <button
        onClick={goToNext}
        className="absolute right-4 top-1/2 -translate-y-1/2 z-10 rounded-full bg-white/90 p-2 shadow-lg transition hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
        aria-label="Next slide"
      >
        <ChevronRight className="h-6 w-6 text-gray-900" />
      </button>

      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10 flex gap-2">
        {images.map((_, index) => (
          <button
            key={index}
            onClick={() => setCurrentIndex(index)}
            className={cn(
              'h-2 rounded-full transition-all',
              index === currentIndex ? 'w-8 bg-white' : 'w-2 bg-white/50 hover:bg-white/75',
            )}
            aria-label={`Go to slide ${index + 1}`}
          />
        ))}
      </div>
    </div>
  );
}
