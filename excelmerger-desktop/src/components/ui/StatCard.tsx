import { Card, CardBody } from "./Card";

export function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="bg-elevated">
      <CardBody className="py-4">
        <div className="text-[12px] text-secondary">{label}</div>
        <div className="mt-1 text-[22px] font-bold text-text">{value}</div>
      </CardBody>
    </Card>
  );
}
