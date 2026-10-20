import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PlatformLogo } from "@/components/PlatformLogo";
import { WhatsAppManagement } from "@/features/whatsapp/WhatsAppManagement";

export function WhatsAppSettings() {
  return (
    <Card id="whatsapp" className="scroll-mt-32 gap-0 overflow-hidden py-0">
      <CardHeader className="border-b p-5 sm:p-6">
        <CardTitle className="flex items-center gap-2">
          <PlatformLogo platform="whatsapp" />
          WhatsApp
        </CardTitle>
        <p className="max-w-prose text-sm/6 text-muted-foreground">
          Conecte sua conta e gerencie grupos, canais, categorias e publicação em um só lugar.
        </p>
      </CardHeader>
      <CardContent className="space-y-6 p-5 sm:p-6">
        <WhatsAppManagement />
      </CardContent>
    </Card>
  );
}
