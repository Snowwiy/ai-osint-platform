import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { EmptyBlock, ErrorBlock, LoadingBlock } from "./StateBlock";
import { getFeatureAvailability } from "../lib/api";
import type { FeatureFlagSettings } from "../types";

export function FeatureGate({
  feature,
  children,
}: {
  feature: keyof FeatureFlagSettings;
  children: ReactNode;
}): JSX.Element {
  const availability = useQuery({
    queryKey: ["feature-availability"],
    queryFn: getFeatureAvailability,
    staleTime: 30_000,
  });

  if (availability.isLoading) {
    return <LoadingBlock label="Checking feature availability" />;
  }
  if (availability.isError) {
    return <ErrorBlock message={availability.error} />;
  }
  if (availability.data?.feature_flags[feature] === false) {
    return (
      <EmptyBlock message="This feature is disabled by an administrator for this deployment." />
    );
  }
  return <>{children}</>;
}
