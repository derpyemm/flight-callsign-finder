const FAMILIES: Record<string, string[]> = {
  A318: ['A318'],
  A319: ['A319', 'A19N'],
  A19N: ['A19N', 'A319'],
  A320: ['A320', 'A20N'],
  A20N: ['A20N', 'A320'],
  A321: ['A321', 'A21N'],
  A21N: ['A21N', 'A321'],
  A332: ['A332', 'A333', 'A339'],
  A333: ['A333', 'A332', 'A339'],
  A339: ['A339', 'A332', 'A333'],
  A342: ['A342', 'A343', 'A345', 'A346'],
  A343: ['A343', 'A342', 'A345', 'A346'],
  A359: ['A359', 'A35K'],
  A35K: ['A35K', 'A359'],
  A388: ['A388'],
  B737: ['B737', 'B738', 'B739', 'B37M', 'B38M', 'B39M'],
  B738: ['B738', 'B38M'],
  B38M: ['B38M', 'B738'],
  B739: ['B739', 'B39M'],
  B39M: ['B39M', 'B739'],
  B744: ['B744', 'B748'],
  B748: ['B748', 'B744'],
  B752: ['B752', 'B753'],
  B763: ['B763', 'B764'],
  B772: ['B772', 'B77L', 'B77W', 'B773'],
  B77W: ['B77W', 'B77L', 'B772'],
  B77L: ['B77L', 'B77W', 'B772'],
  B788: ['B788', 'B789', 'B78X'],
  B789: ['B789', 'B788', 'B78X'],
  B78X: ['B78X', 'B788', 'B789'],
  BCS1: ['BCS1', 'BCS3'],
  BCS3: ['BCS3', 'BCS1'],
  E190: ['E190', 'E195', 'E290', 'E295'],
  E195: ['E195', 'E190', 'E295'],
  CRJ9: ['CRJ9', 'CRJ7', 'CRJ2'],
}

export function expandAircraftTypes(type: string, includeFamily: boolean): string[] {
  const code = type.trim().toUpperCase()
  if (!includeFamily) return [code]
  return FAMILIES[code] ?? [code]
}

export function normalizeIcaoType(value: string): string {
  return value.trim().toUpperCase()
}

export function normalizeIcaoAirport(value: string): string {
  return value.trim().toUpperCase()
}

export function optionalIcaoAirport(value: string | undefined): string | undefined {
  const code = value?.trim().toUpperCase()
  return code || undefined
}
