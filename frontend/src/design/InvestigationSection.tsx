import type { ReactNode } from "react";
import { Panel, PanelBody, PanelHeader } from "./ui/Panel";

interface InvestigationSectionProps {
  index: string;
  title: string;
  children: ReactNode;
  testId: string;
  /** Right-aligned controls or metadata for the section. */
  actions?: ReactNode;
  /** Sub-line clarifying what the section establishes. */
  hint?: ReactNode;
}

/**
 * Numbered forensic-workspace section (evidence chain step).
 *
 * The index is a landmark an engineer navigates by, so it is rendered as a
 * chip rather than as coloured text and the section carries a real
 * accessible name.
 */
export function InvestigationSection({
  index,
  title,
  children,
  testId,
  actions,
  hint,
}: InvestigationSectionProps): React.JSX.Element {
  return (
    <Panel as="section" testId={testId} ariaLabel={`${index} ${title}`} className="scroll-mt-8">
      <PanelHeader index={index} title={title} actions={actions} hint={hint} />
      <PanelBody>{children}</PanelBody>
    </Panel>
  );
}
