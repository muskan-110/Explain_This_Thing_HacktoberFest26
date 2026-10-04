import type { MouseEvent } from 'react'

export interface TapPoint {
  x: number
  y: number
}

interface Props {
  src: string
  marker: TapPoint | null
  onTap: (point: TapPoint) => void
  onImageError?: () => void
  onImageLoad?: () => void
}

const clamp = (n: number) => Math.min(1, Math.max(0, n))

export default function TapImage({ src, marker, onTap, onImageError, onImageLoad }: Props) {
  function handleClick(e: MouseEvent<HTMLImageElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return
    onTap({
      x: clamp((e.clientX - rect.left) / rect.width),
      y: clamp((e.clientY - rect.top) / rect.height),
    })
  }

  return (
    <div className="tap-wrap">
      <img
        src={src}
        alt="Control panel of the appliance"
        className="tap-img"
        onClick={handleClick}
        onError={onImageError}
        onLoad={onImageLoad}
        draggable={false}
      />
      {marker && (
        <span
          className="tap-marker"
          style={{ left: `${marker.x * 100}%`, top: `${marker.y * 100}%` }}
        />
      )}
    </div>
  )
}
